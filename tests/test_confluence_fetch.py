"""Tests for the parts of the Confluence page downloader that need no network."""

from __future__ import annotations

import confluence_fetch
import pytest


def test_page_id_from_url_or_number() -> None:
    url = "https://confluence.example.com/spaces/RFP/pages/123456/Some+Title"
    assert confluence_fetch.page_id_of(url) == "123456"
    assert confluence_fetch.page_id_of("https://x/pages/viewpage.action?pageId=42") == "42"
    assert confluence_fetch.page_id_of("777") == "777"
    with pytest.raises(ValueError):
        confluence_fetch.page_id_of("not-a-page")


def test_local_img_tags_become_markdown_images() -> None:
    tag = '<img src="images/fig1.png" class="x" width="800" alt="Context [C4] view" />'
    md = confluence_fetch.IMG.sub(
        lambda m: f"![{confluence_fetch.alt_of(m.group(0))}]({m.group(1)})", f"before {tag} after"
    )
    assert md == "before ![Context (C4) view](images/fig1.png) after"


def test_remote_images_are_left_alone() -> None:
    tag = '<img src="https://elsewhere/pic.png" alt="x">'
    assert confluence_fetch.IMG.sub("X", tag) == tag
