"""Тесты веб-копии рисунка.

figgybanana рисует 16:9 в 4K — 5632 × 3072 и по 10–13 МБ. Пять таких на странице это
шестьдесят мегабайт, и часть просмотрщиков их просто не показывает. Рендер остаётся в каталоге
прогона инструмента, в статью уходит уменьшенная копия.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

Image = pytest.importorskip("PIL.Image")

import shrink_png


def png(path: Path, width: int, height: int) -> Path:
    Image.new("RGB", (width, height), (200, 220, 240)).save(path)
    return path


def run(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, *argv: str
) -> tuple[dict[str, Any], int]:
    monkeypatch.setattr(sys, "argv", ["shrink_png.py", *argv])
    code = shrink_png.main()
    report: dict[str, Any] = json.loads(capsys.readouterr().out)
    return report, code


def test_wide_render_is_scaled_to_the_limit(tmp_path: Path) -> None:
    src = png(tmp_path / "final_output.png", 5632, 3072)
    dst = tmp_path / "figures" / "fig.png"
    measures, problems = shrink_png.shrink(src, dst, 2000)
    assert problems == []
    assert (measures["width"], measures["height"]) == (2000, 1091)
    assert measures["width_before"] == 5632
    with Image.open(dst) as im:
        assert im.size == (2000, 1091)
    assert dst.stat().st_size < src.stat().st_size


def test_narrow_render_is_copied_not_upscaled(tmp_path: Path) -> None:
    src = png(tmp_path / "small.png", 800, 450)
    measures, problems = shrink_png.shrink(src, tmp_path / "out.png", 2000)
    assert problems == []
    assert (measures["width"], measures["height"]) == (800, 450)


def test_redraw_replaces_the_previous_copy(tmp_path: Path) -> None:
    """Каталог выдачи держит текущую версию рисунка; перерисовка обязана её заменить."""
    dst = tmp_path / "fig.png"
    shrink_png.shrink(png(tmp_path / "a.png", 3000, 1000), dst, 2000)
    shrink_png.shrink(png(tmp_path / "b.png", 3000, 3000), dst, 2000)
    with Image.open(dst) as im:
        assert im.size == (2000, 2000)


def test_missing_source_is_named(tmp_path: Path) -> None:
    measures, problems = shrink_png.shrink(tmp_path / "нет.png", tmp_path / "out.png", 2000)
    assert measures == {}
    assert "source missing" in problems[0]


def test_receipt_goes_to_the_log(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    src = png(tmp_path / "r.png", 4000, 2000)
    log = tmp_path / "tools.jsonl"
    report, code = run(
        capsys,
        monkeypatch,
        "--file",
        str(src),
        "--to",
        str(tmp_path / "f.png"),
        "--max-width",
        "1000",
        "--log",
        str(log),
        "--log-note",
        "web copy of r",
    )
    assert code == 0 and report["ok"] is True
    line = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert line["tool"] == "shrink"
    assert line["measures"]["width"] == 1000
