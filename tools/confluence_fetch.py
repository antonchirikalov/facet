#!/usr/bin/env python3
"""Download a Confluence page as markdown, with its images, into a local folder.

The page body never passes through a model: the tool fetches the rendered HTML (export_view),
downloads every attachment the page uses, rewrites the image links to the local files and
converts the result with pandoc. It is how accepted documents become cases in a local library of
examples; those documents are client material and are kept out of this repository.

Writes <out>/page.md, <out>/images/<files> and <out>/meta.json (id, title, space, version, url).
Credentials come from the environment only, as for confluence_publish.py:
    CONFLUENCE_URL, CONFLUENCE_PERSONAL_TOKEN (or CONFLUENCE_TOKEN).

The output envelope matches gate.py's.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Any

import toollog

PAGE_ID = re.compile(r"(?:pages/|pageId=)(\d+)")
IMG = re.compile(r'<img[^>]*?src="(images/[^"]+)"[^>]*>')
ALT = re.compile(r'alt="([^"]*)"')


def alt_of(tag: str) -> str:
    m = ALT.search(tag)
    return m.group(1).replace("]", ")").replace("[", "(") if m else ""


def page_id_of(ref: str) -> str:
    m = PAGE_ID.search(ref)
    if m:
        return m.group(1)
    if ref.isdigit():
        return ref
    raise ValueError(f"not a page id or a page URL: {ref}")


def fetch(ref: str, out: Path, base: str, token: str) -> dict[str, Any]:
    import httpx

    page_id = page_id_of(ref)
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    with httpx.Client(
        base_url=base.rstrip("/"), headers=headers, timeout=60, follow_redirects=True
    ) as client:
        page = client.get(
            f"/rest/api/content/{page_id}", params={"expand": "body.export_view,version,space"}
        )
        page.raise_for_status()
        data = page.json()
        html = data["body"]["export_view"]["value"]
        attachments = client.get(
            f"/rest/api/content/{page_id}/child/attachment", params={"limit": 500}
        )
        attachments.raise_for_status()
        images = out / "images"
        images.mkdir(parents=True, exist_ok=True)
        saved: list[str] = []
        for att in attachments.json().get("results", []):
            name = att["title"]
            link = att["_links"]["download"]
            got = client.get(link)
            if got.status_code != 200:
                continue
            safe = re.sub(r"[^A-Za-z0-9._-]+", "-", name)
            (images / safe).write_bytes(got.content)
            saved.append(safe)
            # Every way the rendered HTML can point at this attachment becomes the local file.
            for form in {name, urllib.parse.quote(name), urllib.parse.quote(name, safe="")}:
                html = re.sub(
                    r'src="[^"]*/' + re.escape(form) + r'(\?[^"]*)?"',
                    f'src="images/{safe}"',
                    html,
                )
    (out / "page.html").write_text(html, encoding="utf-8")
    pandoc = shutil.which("pandoc")
    if pandoc is None:
        raise RuntimeError("pandoc not found: page.html is saved, page.md is not")
    subprocess.run(
        [
            pandoc,
            str(out / "page.html"),
            "-f",
            "html",
            "-t",
            "gfm",
            "--wrap=none",
            "-o",
            str(out / "page.md"),
        ],
        check=True,
    )
    (out / "page.html").unlink()
    # pandoc keeps an image with attributes as an <img> tag; plain markdown reads the same for an
    # agent and for a person, so local images become ![alt](images/file).
    md = (out / "page.md").read_text(encoding="utf-8")
    md = IMG.sub(lambda m: f"![{alt_of(m.group(0))}]({m.group(1)})", md)
    (out / "page.md").write_text(md, encoding="utf-8")
    # Attachments include old versions and files the page no longer shows; keep what it uses.
    used = set(re.findall(r"\]\(images/([^)]+)\)", md))
    for f in images.iterdir():
        if f.name not in used:
            f.unlink()
    saved = [s for s in saved if s in used]
    meta = {
        "id": page_id,
        "title": data.get("title"),
        "space": (data.get("space") or {}).get("key"),
        "version": (data.get("version") or {}).get("number"),
        "url": f"{base.rstrip('/')}/pages/viewpage.action?pageId={page_id}",
        "images": len(saved),
    }
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def main() -> int:
    p = argparse.ArgumentParser(
        description="Download a Confluence page as markdown with its images."
    )
    p.add_argument("--page", required=True, help="page id or page URL")
    p.add_argument(
        "--out", type=Path, required=True, help="folder to write page.md, images/ and meta.json"
    )
    toollog.add_argument(p)
    args = p.parse_args()
    base = os.environ.get("CONFLUENCE_URL")
    token = os.environ.get("CONFLUENCE_PERSONAL_TOKEN") or os.environ.get("CONFLUENCE_TOKEN")
    problems: list[str] = []
    measures: dict[str, Any] = {}
    if not base or not token:
        problems.append("missing CONFLUENCE_URL or CONFLUENCE_PERSONAL_TOKEN in the environment")
    else:
        try:
            measures = fetch(args.page, args.out, base, token)
        except Exception as exc:  # noqa: BLE001 - the report names any failure
            problems.append(f"{type(exc).__name__}: {str(exc)[:300]}")
    report = {"ok": not problems, "problems": problems, "measures": measures}
    toollog.append(args.log, "confluence_fetch", report, args.log_note, release=args.log_release)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
