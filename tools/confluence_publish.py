#!/usr/bin/env python3
"""Publish a Markdown document to Confluence Server/DC over the REST API.

Why a script and not the MCP path: the MCP markdown->storage conversion merges
consecutive bullet lines that have no blank line before them into a single <p>, so
lists silently collapse -- measured once at 79 <li> shrinking to 29 on a real page.
The converter here is the one that got that page right.

Why not pandoc: it is a second executable to install and verify, and a step's
environment is an allowlist of variable NAMES (I8) -- a missing binary shows up as a
stack trace three retries deep. Everything below is stdlib plus httpx.

Credentials come from the environment only, never from a file:
    CONFLUENCE_URL              e.g. https://confluence.example.com
    CONFLUENCE_PERSONAL_TOKEN   PAT (Bearer); CONFLUENCE_TOKEN accepted as fallback

The result travels as JSON, the way tools/gate.py does it, so the calling agent copies
a record instead of scraping a banner. On failure the JSON names the stage that failed
and the exit code is non-zero.

    python tools/confluence_publish.py --draft doc.md --space KEY --parent-id 123 \
        [--illustrations figures/] [--attachment file.pdf] [--update <pageId>] \
        [--force-new] [--no-toc] [--json out.json] [--dry-run storage.xml]
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:  # pragma: no cover
    import httpx

# httpx is imported where the network is actually touched, not at module load: --dry-run
# and the converter itself must work in an environment that only has the stdlib, which is
# what a content gate over the storage XHTML gets to run in.

# Force UTF-8 on stdout/stderr so a non-ASCII title (e.g. Cyrillic) does not crash
# print() on a cp1252 Windows console. Without this the script dies mid-run and the
# caller falls back to the MCP path, which is the thing this script exists to avoid.
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        try:
            _reconfigure(encoding="utf-8")
        except ValueError:
            pass


class Failure(Exception):
    """A publish that stopped, carrying the stage it stopped at."""

    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage
        self.message = message


# ---------------------------------------------------------------------------
# Markdown -> Confluence storage format
# ---------------------------------------------------------------------------

LIST_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
CHECKBOX_RE = re.compile(r"^\[([ xX])\]\s+")


def _inline(text: str) -> str:
    """Inline markdown -> XHTML: code spans, bold, italic, links."""
    code_spans: list[str] = []

    def _save_code(m: re.Match[str]) -> str:
        escaped = m.group(1).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        code_spans.append(f"<code>{escaped}</code>")
        return f"\x00CODE{len(code_spans) - 1}\x00"

    text = re.sub(r"`([^`]+)`", _save_code, text)

    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*([^*]+)\*(?![\w*])", r"<em>\1</em>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)

    for idx, span in enumerate(code_spans):
        text = text.replace(f"\x00CODE{idx}\x00", span)

    return text


_TASK_SEQ = [0]


def _task_checkbox(complete: bool) -> str:
    """A real Confluence checkbox: tickable on the published page without editing it."""
    _TASK_SEQ[0] += 1
    status = "complete" if complete else "incomplete"
    return (
        "<ac:task-list><ac:task>"
        f"<ac:task-id>{_TASK_SEQ[0]}</ac:task-id>"
        f"<ac:task-status>{status}</ac:task-status>"
        "<ac:task-body />"
        "</ac:task></ac:task-list>"
    )


def _cell_to_xhtml(cell: str) -> str:
    """A table cell that may carry <br>-separated lines and bullet characters."""
    stripped = cell.strip()
    if stripped in ("[ ]", "[]"):
        return _task_checkbox(False)
    if stripped.lower() in ("[x]", "[х]"):
        return _task_checkbox(True)
    if "<br>" not in cell and "•" not in cell:
        return _inline(cell)

    parts = cell.split("<br>")
    html_parts: list[str] = []
    bullets: list[str] = []

    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part.startswith("•"):
            bullets.append(f"<li>{_inline(part[1:].strip())}</li>")
        else:
            if bullets:
                html_parts.append("<ul>" + "".join(bullets) + "</ul>")
                bullets = []
            html_parts.append(f"<p>{_inline(part)}</p>")

    if bullets:
        html_parts.append("<ul>" + "".join(bullets) + "</ul>")

    return "".join(html_parts)


def _convert_table(md_table: str) -> str:
    lines = [row.strip() for row in md_table.strip().splitlines() if row.strip()]
    if len(lines) < 2:
        return md_table

    def _parse_row(row: str) -> list[str]:
        return [c.strip() for c in row.strip().strip("|").split("|")]

    header_cells = _parse_row(lines[0])
    body_rows = [_parse_row(row) for row in lines[2:]]  # lines[1] is the |---|---| rule

    html = '<table class="wrapped"><colgroup>'
    html += "<col />" * len(header_cells)
    html += "</colgroup><thead><tr>"
    for cell in header_cells:
        html += f"<th>{_inline(cell)}</th>"
    html += "</tr></thead><tbody>"
    for row in body_rows:
        html += "<tr>"
        for cell in row:
            html += f"<td>{_cell_to_xhtml(cell)}</td>"
        html += "</tr>"
    html += "</tbody></table>"
    return html


def _indent_of(line: str) -> int:
    expanded = line.expandtabs(4)
    return len(expanded) - len(expanded.lstrip())


def _collect_list(lines: list[str], i: int) -> tuple[list[tuple[int, str, str]], int]:
    """Gather one list block as flat (indent, marker, text) triples.

    A run of blank lines inside a list is kept inside it: items separated by an empty
    line are still one list, and cutting there is what produced a string of one-item
    <ul>s. A deeper line that is not a marker continues the item above, so a wrapped
    bullet does not become a paragraph of its own.

    Crossing a blank line requires the next item to belong to THIS list: deeper, or at
    the same indent with the same kind of marker. Without the kind check a numbered list
    following a bulleted one is absorbed into it as flat items -- caught by the test
    document, not by reasoning.
    """
    base_indent = _indent_of(lines[i])
    first = LIST_RE.match(lines[i])
    base_ordered = bool(first and first.group(2)[0].isdigit())
    block: list[tuple[int, str, str]] = []

    while i < len(lines):
        line = lines[i]

        if not line.strip():
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            nxt = LIST_RE.match(lines[j]) if j < len(lines) else None
            if nxt:
                nxt_indent = _indent_of(lines[j])
                nxt_ordered = nxt.group(2)[0].isdigit()
                if nxt_indent > base_indent or (
                    nxt_indent == base_indent and nxt_ordered == base_ordered
                ):
                    i = j
                    continue
            break

        m = LIST_RE.match(line)
        if m:
            indent = _indent_of(line)
            if indent < base_indent:
                break
            block.append((indent, m.group(2), m.group(3).strip()))
            i += 1
            continue

        if block and _indent_of(line) > base_indent:
            indent, marker, text = block[-1]
            block[-1] = (indent, marker, (text + " " + line.strip()).strip())
            i += 1
            continue

        break

    return block, i


def _build_list(
    block: list[tuple[int, str, str]], pos: int, indent: int
) -> tuple[dict[str, Any], int]:
    items: list[dict[str, Any]] = []
    ordered: bool | None = None

    while pos < len(block):
        item_indent, marker, text = block[pos]
        if item_indent < indent:
            break
        if item_indent > indent:
            sub, pos = _build_list(block, pos, item_indent)
            if items:
                items[-1]["sub"].append(sub)
            else:
                return sub, pos
            continue
        if ordered is None:
            ordered = marker[0].isdigit()
        items.append({"text": text, "sub": []})
        pos += 1

    return {"ordered": bool(ordered), "items": items}, pos


def _render_list(node: dict[str, Any]) -> str:
    tag = "ol" if node["ordered"] else "ul"
    out = f"<{tag}>"
    for item in node["items"]:
        text = item["text"]
        box = CHECKBOX_RE.match(text)
        if box:
            mark = "☑" if box.group(1).lower() == "x" else "☐"
            text = f"{mark} {text[box.end() :]}"
        out += "<li>" + _inline(text)
        for sub in item["sub"]:
            out += _render_list(sub)
        out += "</li>"
    return out + f"</{tag}>"


def md_to_confluence(md: str) -> str:
    """Markdown -> Confluence storage format XHTML."""
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    in_code = False
    code_lang = ""
    code_lines: list[str] = []
    in_table = False
    table_lines: list[str] = []

    def _flush_table() -> None:
        nonlocal in_table, table_lines
        if table_lines:
            out.append(_convert_table("\n".join(table_lines)))
            table_lines = []
        in_table = False

    while i < len(lines):
        line = lines[i]

        # --- fenced code first, so nothing inside a fence gets interpreted ---
        if line.strip().startswith("```") and not in_code:
            _flush_table()
            in_code = True
            code_lang = line.strip().lstrip("`").strip()
            code_lines = []
            i += 1
            continue
        if line.strip().startswith("```") and in_code:
            lang_attr = f' ac:language="{code_lang}"' if code_lang else ""
            body = "\n".join(code_lines).replace("]]>", "]]]]><![CDATA[>")
            out.append(
                f'<ac:structured-macro ac:name="code"{lang_attr}>'
                f"<ac:plain-text-body><![CDATA[{body}]]></ac:plain-text-body>"
                f"</ac:structured-macro>"
            )
            in_code = False
            code_lang = ""
            code_lines = []
            i += 1
            continue
        if in_code:
            code_lines.append(line)
            i += 1
            continue

        # --- GFM alert blocks: > [!WARNING] and friends ---
        alert_m = re.match(
            r"^>\s*\[!(WARNING|NOTE|INFO|TIP|CAUTION)\]\s*$", line.strip(), re.IGNORECASE
        )
        if alert_m:
            _flush_table()
            macro_name = {
                "WARNING": "warning",
                "CAUTION": "warning",
                "NOTE": "note",
                "INFO": "info",
                "TIP": "tip",
            }.get(alert_m.group(1).upper(), "note")
            i += 1
            body_lines: list[str] = []
            while i < len(lines) and lines[i].startswith(">"):
                body_lines.append(re.sub(r"^>\s?", "", lines[i]))
                i += 1
            inner = md_to_confluence("\n".join(body_lines))
            out.append(
                f'<ac:structured-macro ac:name="{macro_name}">'
                f"<ac:rich-text-body>{inner}</ac:rich-text-body>"
                f"</ac:structured-macro>"
            )
            continue

        # --- blockquote ---
        if line.strip().startswith(">"):
            _flush_table()
            bq_lines: list[str] = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                bq_lines.append(re.sub(r"^>\s?", "", lines[i]))
                i += 1
            inner = md_to_confluence("\n".join(bq_lines))
            out.append(f"<blockquote>{inner}</blockquote>")
            continue

        # --- tables ---
        if re.match(r"^\s*\|", line):
            in_table = True
            table_lines.append(line)
            i += 1
            continue
        if in_table:
            _flush_table()

        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            out.append("<hr />")
            i += 1
            continue

        m = re.match(r"^(#{1,6})\s+(.*)", stripped)
        if m:
            level = len(m.group(1))
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            i += 1
            continue

        # --- standalone image -> attachment reference ---
        m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$", stripped)
        if m:
            alt = (
                m.group(1)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
            )
            filename = Path(m.group(2)).name
            out.append(
                f'<p><ac:image ac:alt="{alt}" ac:width="800">'
                f'<ri:attachment ri:filename="{filename}" />'
                f"</ac:image></p>"
            )
            i += 1
            continue

        # --- lists, nesting preserved ---
        if LIST_RE.match(line):
            block, i = _collect_list(lines, i)
            if block:
                node, _ = _build_list(block, 0, block[0][0])
                out.append(_render_list(node))
            continue

        # --- paragraph ---
        para_lines = [stripped]
        i += 1
        while i < len(lines):
            nxt = lines[i]
            if not nxt.strip():
                break
            s = nxt.strip()
            if (
                s.startswith(("#", "```", ">", "!["))
                or re.match(r"^\s*\|", nxt)
                or re.match(r"^(-{3,}|\*{3,}|_{3,})$", s)
                or LIST_RE.match(nxt)
            ):
                break
            para_lines.append(s)
            i += 1
        out.append(f"<p>{_inline(' '.join(para_lines))}</p>")

    _flush_table()
    return "\n".join(out)


TOC_MACRO = (
    '<ac:structured-macro ac:name="toc">'
    '<ac:parameter ac:name="minLevel">1</ac:parameter>'
    '<ac:parameter ac:name="maxLevel">3</ac:parameter>'
    '<ac:parameter ac:name="printable">true</ac:parameter>'
    "</ac:structured-macro>"
)


# ---------------------------------------------------------------------------
# Confluence REST
# ---------------------------------------------------------------------------


def get_client(base_url: str, token: str) -> httpx.Client:
    try:
        import httpx
    except ImportError as exc:  # pragma: no cover - runtime guard
        raise Failure("config", "httpx is not installed in this environment") from exc

    return httpx.Client(
        base_url=base_url.rstrip("/"),
        headers={
            "Authorization": f"Bearer {token}",
            "X-Atlassian-Token": "no-check",
        },
        timeout=60.0,
    )


def read_page(client: httpx.Client, page_id: str, stage: str) -> dict[str, Any]:
    resp = client.get(f"/rest/api/content/{page_id}", params={"expand": "version,space"})
    if resp.status_code != 200:
        raise Failure(
            stage, f"cannot read page {page_id}: HTTP {resp.status_code} {resp.text[:300]}"
        )
    return cast("dict[str, Any]", resp.json())


def find_child_by_title(client: httpx.Client, parent_id: str, title: str) -> dict[str, Any] | None:
    """The upsert key: a page is identified by its title under its parent.

    Without this the agent, which never knows a page id, creates a duplicate on every
    republish -- while its prompt promises it updates in place.
    """
    start = 0
    limit = 100
    while True:
        resp = client.get(
            f"/rest/api/content/{parent_id}/child/page",
            params={"limit": limit, "start": start, "expand": "version"},
        )
        if resp.status_code != 200:
            raise Failure("lookup", f"cannot list children of {parent_id}: HTTP {resp.status_code}")
        data = resp.json()
        results: list[dict[str, Any]] = data.get("results", [])
        for child in results:
            if child.get("title", "").strip() == title.strip():
                return child
        if len(results) < limit:
            return None
        start += limit


def create_page(
    client: httpx.Client, space_key: str, parent_id: str, title: str, body: str
) -> dict[str, Any]:
    payload = {
        "type": "page",
        "title": title,
        "ancestors": [{"id": parent_id}],
        "space": {"key": space_key},
        "body": {"storage": {"value": body, "representation": "storage"}},
    }
    resp = client.post(
        "/rest/api/content", json=payload, headers={"Content-Type": "application/json"}
    )
    if resp.status_code not in (200, 201):
        raise Failure("create", f"HTTP {resp.status_code} {resp.text[:500]}")
    return cast("dict[str, Any]", resp.json())


def update_page(client: httpx.Client, page_id: str, title: str, body: str) -> dict[str, Any]:
    current = read_page(client, page_id, "update")
    version = current["version"]["number"] + 1
    payload = {
        "type": "page",
        "title": title,
        "version": {"number": version, "minorEdit": True},
        "body": {"storage": {"value": body, "representation": "storage"}},
    }
    resp = client.put(
        f"/rest/api/content/{page_id}", json=payload, headers={"Content-Type": "application/json"}
    )
    if resp.status_code not in (200, 201):
        raise Failure("update", f"HTTP {resp.status_code} {resp.text[:500]}")
    return cast("dict[str, Any]", resp.json())


def upload_attachment(client: httpx.Client, page_id: str, path: Path) -> tuple[bool, str]:
    """Upload, replacing the data of a same-named attachment when one is already there."""
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"

    with path.open("rb") as fh:
        resp = client.post(
            f"/rest/api/content/{page_id}/child/attachment",
            files={"file": (path.name, fh, mime)},
        )

    if resp.status_code == 400 and "same file name" in resp.text:
        listing = client.get(
            f"/rest/api/content/{page_id}/child/attachment", params={"filename": path.name}
        )
        results = listing.json().get("results", []) if listing.status_code == 200 else []
        if results:
            att_id = results[0]["id"]
            with path.open("rb") as fh:
                resp = client.post(
                    f"/rest/api/content/{page_id}/child/attachment/{att_id}/data",
                    files={"file": (path.name, fh, mime)},
                )

    if resp.status_code not in (200, 201):
        return False, f"HTTP {resp.status_code} {resp.text[:200]}"
    return True, ""


# ---------------------------------------------------------------------------


def first_h1(md: str, fallback: str) -> str:
    m = re.search(r"^#\s+(.+)$", md, re.MULTILINE)
    return m.group(1).strip() if m else fallback


def resolve_attachments(
    md: str, illustrations: Path | None, extra: list[str]
) -> tuple[list[Path], list[str]]:
    """Only the images the document references, plus explicit --attachment files.

    A folder of generated figures also carries backups (*_v1_orig.png); attaching those
    puts files on the page that nothing on it points at.
    """
    files: list[Path] = []
    skipped: list[str] = []

    if illustrations is not None:
        referenced = {Path(src).name for src in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", md)}
        candidates = sorted(p for p in illustrations.iterdir() if p.is_file())
        matched = [p for p in candidates if p.name in referenced]
        if matched:
            files.extend(matched)
            skipped = [p.name for p in candidates if p.name not in referenced]
        else:
            files.extend(p for p in candidates if p.suffix.lower() == ".png")

    for item in extra:
        path = Path(item).expanduser()
        if not path.is_file():
            raise Failure("config", f"attachment not found: {path}")
        files.append(path)

    return files, skipped


def run(args: argparse.Namespace) -> dict[str, Any]:
    draft = Path(args.draft).expanduser()
    if not draft.is_file():
        raise Failure("config", f"draft not found: {draft}")

    md = draft.read_text(encoding="utf-8")
    title = args.title or first_h1(md, draft.stem)

    illustrations: Path | None = None
    if args.illustrations:
        illustrations = Path(args.illustrations).expanduser()
        if not illustrations.is_dir():
            raise Failure("config", f"illustrations folder not found: {illustrations}")

    attachments, skipped = resolve_attachments(md, illustrations, args.attachment)

    body = md_to_confluence(md)
    if not args.no_toc:
        body = TOC_MACRO + "\n" + body

    if args.dry_run:
        out_path = Path(args.dry_run).expanduser()
        out_path.write_text(body, encoding="utf-8")
        return {
            "action": "dry-run",
            "title": title,
            "storage_chars": len(body),
            "storage_file": str(out_path),
            "attachments": [p.name for p in attachments],
            "attachments_count": len(attachments),
            "attachments_skipped": skipped,
        }

    url = os.environ.get("CONFLUENCE_URL")
    token = os.environ.get("CONFLUENCE_PERSONAL_TOKEN") or os.environ.get("CONFLUENCE_TOKEN")
    missing = [
        name
        for name, value in (("CONFLUENCE_URL", url), ("CONFLUENCE_PERSONAL_TOKEN", token))
        if not value
    ]
    if missing:
        raise Failure("config", "missing environment variable(s): " + ", ".join(missing))
    assert url is not None and token is not None

    if not args.update and not args.parent_id:
        raise Failure("config", "provide --parent-id (create or upsert) or --update <pageId>")

    client = get_client(url, token)
    try:
        space = args.space
        page_id = args.update
        action = "updated"

        if page_id:
            existing = read_page(client, page_id, "lookup")
            space = space or existing.get("space", {}).get("key")
        else:
            parent = read_page(client, args.parent_id, "parent")
            space = space or parent.get("space", {}).get("key")
            if not space:
                raise Failure(
                    "config", "--space is required and could not be inferred from the parent"
                )
            if not args.force_new:
                child = find_child_by_title(client, args.parent_id, title)
                if child:
                    page_id = child["id"]

        if page_id:
            page = update_page(client, page_id, title, body)
        else:
            page = create_page(client, space, args.parent_id, title, body)
            page_id = page["id"]
            action = "created"

        uploaded: list[str] = []
        failed: list[dict[str, str]] = []
        for path in attachments:
            ok, reason = upload_attachment(client, page_id, path)
            if ok:
                uploaded.append(path.name)
            else:
                failed.append({"file": path.name, "reason": reason})

        links = page.get("_links", {})
        base = links.get("base") or url.rstrip("/")
        webui = links.get("webui") or f"/pages/viewpage.action?pageId={page_id}"

        return {
            "action": action,
            "url": base.rstrip("/") + webui,
            "page_id": str(page_id),
            "title": page.get("title", title),
            "space": space,
            "parent_id": args.parent_id,
            "version": page.get("version", {}).get("number"),
            "storage_chars": len(body),
            "attachments": uploaded,
            "attachments_count": len(uploaded),
            "attachments_failed": failed,
            "attachments_skipped": skipped,
        }
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish Markdown to Confluence Server/DC")
    parser.add_argument("--draft", required=True, help="Markdown file to publish")
    parser.add_argument(
        "--space", default=None, help="Space key (inferred from the parent when omitted)"
    )
    parser.add_argument(
        "--parent-id", default=None, help="Parent page id; required unless --update"
    )
    parser.add_argument("--title", default=None, help="Page title (default: first H1)")
    parser.add_argument("--update", default=None, help="Update this page id directly")
    parser.add_argument(
        "--force-new",
        action="store_true",
        help="Create a new page even if a child with the same title exists",
    )
    parser.add_argument("--illustrations", default=None, help="Folder with referenced images")
    parser.add_argument(
        "--attachment", action="append", default=[], help="Extra file to attach; repeatable"
    )
    parser.add_argument(
        "--no-toc", action="store_true", help="Do not prepend the Table of Contents macro"
    )
    parser.add_argument(
        "--json", dest="json_out", default=None, help="Write the result record to this path"
    )
    parser.add_argument(
        "--dry-run",
        default=None,
        help="Convert only: write storage XHTML here, touch nothing remote",
    )
    args = parser.parse_args()

    try:
        result = run(args)
    except Failure as exc:
        record: dict[str, Any] = {"ok": False, "stage": exc.stage, "error": exc.message}
        if args.json_out:
            Path(args.json_out).expanduser().write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        print(json.dumps(record, ensure_ascii=False, indent=2))
        sys.exit(1)

    record = {"ok": True, **result}
    if args.json_out:
        Path(args.json_out).expanduser().write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
