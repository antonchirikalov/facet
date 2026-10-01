"""Tests for the markdown -> Confluence storage format converter.

The converter is tested, not REST: the tests never touch the network, and the whole class of
defects this script exists for lives in the converter. The original defect of the MCP path:
bullets that follow a paragraph without a blank line were glued into one <p>, and the list
vanished (live measurement: 79 <li> became 29). So the first test is about a list right after a
paragraph, and the rest cover what broke while the logic was being moved.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import confluence_publish as cp
import pytest


def _count(pattern: str, text: str) -> int:
    return len(re.findall(pattern, text))


def test_list_right_after_a_paragraph_stays_a_list() -> None:
    """The original defect: no blank line before the bullets."""
    md = "Text, and a list right away:\n- one\n- two\n- three\n"
    out = cp.md_to_confluence(md)
    assert _count(r"<li>", out) == 3
    assert "<ul>" in out
    assert "<p>Text, and a list right away:</p>" in out


def test_nesting_by_indent_is_kept() -> None:
    md = "- one\n- two\n  - nested\n    - deeper\n- three\n"
    out = cp.md_to_confluence(md)
    # three levels of <ul>, five items, and the nested list sits INSIDE an <li>
    assert _count(r"<ul>", out) == 3
    assert _count(r"<li>", out) == 5
    assert "<li>two<ul>" in out


def test_numbered_list_after_bullets_does_not_stick_to_them() -> None:
    """Across a blank line a list continues only with a marker of the same kind.

    Without the marker-kind check, a numbered list was swallowed by the preceding <ul> as flat
    items; a test document caught it, not reasoning.
    """
    md = "- one\n- two\n\n1. first\n2. second\n"
    out = cp.md_to_confluence(md)
    assert out.count("<ul>") == 1
    assert out.count("<ol>") == 1
    assert _count(r"<li>", out) == 4


def test_blank_line_inside_a_list_does_not_break_it() -> None:
    """Items separated by a blank line are one list (a loose list in markdown)."""
    md = "- one\n\n- two\n\n- three\n"
    out = cp.md_to_confluence(md)
    assert out.count("<ul>") == 1
    assert _count(r"<li>", out) == 3


def test_line_break_continues_the_item_instead_of_starting_a_paragraph() -> None:
    md = "- an item that\n  continues below\n- second\n"
    out = cp.md_to_confluence(md)
    assert "<li>an item that continues below</li>" in out
    assert "<p>" not in out


def test_two_tables_in_a_row_do_not_merge() -> None:
    md = "| A | B |\n|---|---|\n| 1 | 2 |\n\nA paragraph between them.\n\n| C | D |\n|---|---|\n| 3 | 4 |\n"
    out = cp.md_to_confluence(md)
    assert out.count("<table") == 2
    assert out.count("<th>") == 4


def test_code_is_not_read_as_markdown() -> None:
    md = "```python\nx = 1 if a < b else 2\n# - not a list\n```\n"
    out = cp.md_to_confluence(md)
    assert 'ac:name="code"' in out
    assert 'ac:language="python"' in out
    assert "<li>" not in out
    assert "a < b" in out  # inside CDATA escaping is neither needed nor done


def test_links_bold_and_inline_code() -> None:
    md = "See **important** and `code`, and [a link](https://example.com).\n"
    out = cp.md_to_confluence(md)
    assert "<strong>important</strong>" in out
    assert "<code>code</code>" in out
    assert '<a href="https://example.com">a link</a>' in out


def test_underscore_in_an_identifier_does_not_become_italic() -> None:
    md = "The field *important* is italic, but `snake_case_name` and 2*3*4 are not.\n"
    out = cp.md_to_confluence(md)
    assert "<em>important</em>" in out
    assert "<code>snake_case_name</code>" in out


def test_image_becomes_an_attachment_reference() -> None:
    md = "![Flow diagram](figures/flow.png)\n"
    out = cp.md_to_confluence(md)
    assert '<ri:attachment ri:filename="flow.png" />' in out
    assert 'ac:alt="Flow diagram"' in out


def test_alert_becomes_a_macro_with_a_nested_list() -> None:
    md = "> [!WARNING]\n> Careful\n> - and a list inside\n"
    out = cp.md_to_confluence(md)
    assert 'ac:name="warning"' in out
    assert "<li>and a list inside</li>" in out


def test_checkboxes_show_in_the_item_text() -> None:
    md = "- [ ] not done\n- [x] done\n"
    out = cp.md_to_confluence(md)
    assert "☐ not done" in out
    assert "☑ done" in out


def test_html_is_escaped_not_leaked_into_markup() -> None:
    md = "Comparing a < b and a <script> tag in the text.\n"
    out = cp.md_to_confluence(md)
    assert "&lt;script&gt;" in out
    assert "<script>" not in out


# ---------------------------------------------------------------------------
# Attachments: the agent publishes the document, not the contents of the folder
# ---------------------------------------------------------------------------


def test_only_referenced_images_are_attached(tmp_path: Path) -> None:
    """The generated figures folder also holds backup copies; they must not reach the page."""
    figures = tmp_path / "figures"
    figures.mkdir()
    for name in ("flow.png", "flow_v1_orig.png", "unused.png"):
        (figures / name).write_bytes(b"\x89PNG")

    md = "![Diagram](figures/flow.png)\n"
    files, skipped = cp.resolve_attachments(md, figures, [])

    assert [p.name for p in files] == ["flow.png"]
    assert set(skipped) == {"flow_v1_orig.png", "unused.png"}


def test_without_references_every_png_is_taken(tmp_path: Path) -> None:
    figures = tmp_path / "figures"
    figures.mkdir()
    (figures / "a.png").write_bytes(b"\x89PNG")
    (figures / "notes.txt").write_text("x", encoding="utf-8")

    files, skipped = cp.resolve_attachments("No images.\n", figures, [])

    assert [p.name for p in files] == ["a.png"]
    assert skipped == []


def test_missing_attachment_fails_with_the_stage_name(tmp_path: Path) -> None:
    with pytest.raises(cp.Failure) as exc:
        cp.resolve_attachments("", None, [str(tmp_path / "missing.pdf")])
    assert exc.value.stage == "config"


def test_title_comes_from_the_first_h1() -> None:
    assert cp.first_h1("# Title\n\ntext\n", "fallback") == "Title"
    assert cp.first_h1("text without a heading\n", "fallback") == "fallback"


# --- internal documents do not leave verbatim ------------------------------------------------


def test_internal_document_marker_is_found_in_the_header() -> None:
    # The Russian marker is data: drafts are Russian, and the tool must recognise their wording.
    assert cp.internal_marker(
        "# Бриф\n\nВнутренний документ для команды продажи, клиенту не показывать."
    )
    assert cp.internal_marker("# Client research notes (internal)\n\ntext")
    assert cp.internal_marker("# Design\n\nThe PDF service is an internal tool.") is None


def test_internal_draft_is_not_published(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    draft = tmp_path / "brief.md"
    draft.write_text("# Бриф\n\nВнутренний документ, клиенту не показывать.\n", encoding="utf-8")
    monkeypatch.setenv("CONFLUENCE_URL", "https://example.invalid")
    monkeypatch.setenv("CONFLUENCE_PERSONAL_TOKEN", "t")
    args = argparse.Namespace(
        draft=str(draft),
        title=None,
        illustrations=None,
        attachment=[],
        no_toc=True,
        dry_run=None,
        allow_internal=False,
    )
    with pytest.raises(cp.Failure) as exc:
        cp.run(args)
    assert exc.value.stage == "policy"
