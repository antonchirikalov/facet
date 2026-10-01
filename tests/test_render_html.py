"""An exact screen is rendered from HTML: what the markup says is what the image shows.

The tests do not start the browser itself; they check how it is found and with what command it
is called.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import render_html


def test_explicit_path_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = tmp_path / "chrome.exe"
    fake.write_bytes(b"")
    monkeypatch.setenv("CHROME_BIN", str(tmp_path / "other.exe"))
    assert render_html.locate(str(fake)) == str(fake)


def test_command_is_headless_with_viewport_and_scale(tmp_path: Path) -> None:
    html = tmp_path / "screen.html"
    html.write_text("<p>6 posts</p>", encoding="utf-8")
    argv = render_html.command("chrome", html, tmp_path / "out.png", 1600, 900, 2.0)
    assert argv[0] == "chrome" and "--headless=new" in argv
    assert "--window-size=1600,900" in argv and "--force-device-scale-factor=2" in argv
    assert argv[-1].startswith("file:///")


def test_missing_html_is_a_problem(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["render_html.py", "--html", str(tmp_path / "x.html"), "--out", str(tmp_path / "x.png")],
    )
    render_html.main()
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is False and report["problems"][0].startswith("file missing")
