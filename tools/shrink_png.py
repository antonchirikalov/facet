#!/usr/bin/env python3
"""Make a web-sized copy of a rendered figure.

figgybanana renders 16:9 figures at 4K — 5632 × 3072 and 10–13 MB each. That is the right
file to keep for a redraw and the wrong file to ship: a page with five of them weighs sixty
megabytes, and half the markdown previewers on a laptop stop showing them at all. So the
render stays in the tool's own run directory and the article gets a copy scaled to a width a
page can carry.

It is a copy with a resize, in the family of snapshot.py: it transforms a file the workflow
already produced, decides nothing, and leaves a receipt. It needs Pillow, which the workflow
finds in figgybanana's own virtualenv — the one interpreter on the machine that is guaranteed
to have it, because figgybanana cannot run without it. Run it with that python.

    "<figgybanana>/.venv/Scripts/python.exe" -X utf8 tools/shrink_png.py \\
        --file <run>/final_output.png --to figures/<slug>.png --max-width 2000
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import toollog


def shrink(source: Path, target: Path, max_width: int) -> tuple[dict[str, object], list[str]]:
    """Copy `source` to `target`, scaled down to at most `max_width` pixels wide.

    Never scales up: a render narrower than the limit is copied as it is. Overwrites the
    target on purpose — the delivery directory holds the current version of a figure, and a
    redraw is meant to replace the one before it.
    """
    problems: list[str] = []
    measures: dict[str, object] = {}
    if not source.is_file():
        return measures, [f"source missing: {source.as_posix()}"]
    try:
        from PIL import Image
    except ImportError:
        return measures, [
            "Pillow is not installed in this interpreter: run with figgybanana's python"
        ]

    with Image.open(source) as im:
        width, height = im.size
        measures["width_before"] = width
        measures["height_before"] = height
        if width > max_width:
            scale = max_width / width
            im = im.resize((max_width, max(1, round(height * scale))), Image.LANCZOS)
        target.parent.mkdir(parents=True, exist_ok=True)
        im.save(target, format="PNG", optimize=True)
        measures["width"], measures["height"] = im.size

    measures["bytes_before"] = source.stat().st_size
    measures["bytes"] = target.stat().st_size
    return measures, problems


def main() -> int:
    p = argparse.ArgumentParser(description="Web-sized copy of a rendered PNG.")
    p.add_argument("--file", dest="source", type=Path, required=True, help="the render")
    p.add_argument("--to", dest="target", type=Path, required=True, help="where the copy goes")
    p.add_argument("--max-width", type=int, default=2000, help="pixels; never scales up")
    p.add_argument("--strict", action="store_true", help="also exit 1 when nothing was written")
    toollog.add_argument(p)
    args = p.parse_args()

    measures, problems = shrink(args.source, args.target, args.max_width)
    report = {"ok": not problems, "problems": problems, "measures": measures}
    toollog.append(args.log, "shrink", report, args.log_note, release=args.log_release)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if (problems and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
