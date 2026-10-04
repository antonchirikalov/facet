#!/usr/bin/env python3
"""Render an HTML mockup to a PNG with headless Chrome: the deterministic path for exact screens.

A generator draws a convincing tablet screen and gets its numbers wrong: six posts become five
or seven, a dimension appears twice, a disclaimer loses a word. On one live proposal a screen
took thirty candidates and still needed its text fixed by hand. An exact screen is therefore
written as HTML and CSS by the illustrator, in the look of the figures already accepted, and
rendered here: what the HTML says is what the PNG shows, every time.

The browser is found in this order: --chrome, $CHROME_BIN, the usual install paths of Chrome and
Edge, then chrome, chromium and msedge on PATH. Exit code is 0 either way; the verdict travels in
the JSON, with the command that was run.

An animated scene is rendered one step at a time: --fragment "step=3" opens the page at
scene.html#step=3, which the animated-scene profile requires to show step 3 with its animation
finished, and --wait-ms lets the page's timers run that long in virtual time before the shot.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

import toollog

CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)
ON_PATH = ("chrome", "google-chrome", "chromium", "chromium-browser", "msedge")


def locate(explicit: str | None) -> str | None:
    for candidate in (explicit, os.environ.get("CHROME_BIN"), *CANDIDATES):
        if candidate and Path(candidate).is_file():
            return candidate
    for name in ON_PATH:
        found = shutil.which(name)
        if found:
            return found
    return None


def command(
    browser: str,
    html: Path,
    png: Path,
    width: int,
    height: int,
    scale: float,
    fragment: str = "",
    wait_ms: int = 0,
) -> list[str]:
    uri = html.resolve().as_uri() + (f"#{fragment}" if fragment else "")
    return [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--no-first-run",
        f"--force-device-scale-factor={scale:g}",
        f"--window-size={width},{height}",
        *([f"--virtual-time-budget={wait_ms}"] if wait_ms else []),
        f"--screenshot={png.resolve()}",
        uri,
    ]


def main() -> int:
    p = argparse.ArgumentParser(description="Render an HTML mockup to PNG with headless Chrome.")
    p.add_argument(
        "--html", type=Path, required=True, help="the mockup, a self-contained HTML file"
    )
    p.add_argument("--out", type=Path, required=True, help="the PNG to write")
    p.add_argument("--width", type=int, default=1600, help="viewport width in CSS pixels")
    p.add_argument("--height", type=int, default=900, help="viewport height in CSS pixels")
    p.add_argument("--scale", type=float, default=2.0, help="device scale factor")
    p.add_argument("--chrome", help="path to the browser")
    p.add_argument(
        "--fragment", default="", help='URL fragment, e.g. "step=3" for one step of a scene'
    )
    p.add_argument(
        "--wait-ms", type=int, default=0, help="virtual time the page runs before the screenshot"
    )
    toollog.add_argument(p)
    args = p.parse_args()

    problems: list[str] = []
    measures: dict[str, object] = {}
    browser = locate(args.chrome)
    if not args.html.is_file():
        problems.append(f"file missing: {args.html.as_posix()}")
    elif browser is None:
        problems.append("no Chrome or Edge found: pass --chrome or set CHROME_BIN")
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        argv = command(
            browser,
            args.html,
            args.out,
            args.width,
            args.height,
            args.scale,
            args.fragment,
            args.wait_ms,
        )
        measures["command"] = argv
        done = subprocess.run(argv, capture_output=True, text=True, timeout=120, check=False)
        if not args.out.is_file() or args.out.stat().st_size == 0:
            problems.append(
                f"no PNG written (exit {done.returncode}): {done.stderr.strip()[-300:]}"
            )
        else:
            measures["bytes"] = args.out.stat().st_size
    report = {"ok": not problems, "problems": problems, "measures": measures}
    toollog.append(args.log, "render_html", report, args.log_note, release=args.log_release)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
