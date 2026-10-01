"""Tests for the sweeper: it walks the repository root, so it must not make mistakes.

The tests check exactly what one fears from it: that it leaves a working directory alone, does
not delete a directory holding even one file, and that `--dry-run` really removes nothing.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import sweep_junk


def make_root(tmp_path: Path) -> Path:
    """A snapshot of the root: our own directories, a foreign empty one and a foreign one with a file."""
    (tmp_path / "facet").mkdir()
    (tmp_path / "tools").mkdir()
    (tmp_path / "probe-runs" / "attn").mkdir(parents=True)
    (tmp_path / "probe-runs" / "attn" / "article.md").write_text("text", encoding="utf-8")
    (tmp_path / "OF_PROCESSORS=16").mkdir()
    (tmp_path / "ৠ翹").mkdir()
    (tmp_path / "Shell" / "v1.0").mkdir(parents=True)
    (tmp_path / "important").mkdir()
    (tmp_path / "important" / "file.txt").write_text("do not delete", encoding="utf-8")
    (tmp_path / "README.md").write_text("a file in the root", encoding="utf-8")
    return tmp_path


def test_splits_empty_from_occupied(tmp_path: Path) -> None:
    empty, occupied = sweep_junk.strays(make_root(tmp_path))
    assert {p.name for p in empty} == {"OF_PROCESSORS=16", "ৠ翹", "Shell"}
    assert {p.name for p in occupied} == {"important"}


def test_keeps_the_repository_own_directories(tmp_path: Path) -> None:
    empty, occupied = sweep_junk.strays(make_root(tmp_path))
    names = {p.name for p in empty + occupied}
    assert "facet" not in names
    assert "tools" not in names
    assert "probe-runs" not in names


def test_nested_empty_directory_counts_as_empty(tmp_path: Path) -> None:
    """`Shell/v1.0` is a directory inside a directory without a single file; that is junk too."""
    empty, _ = sweep_junk.strays(make_root(tmp_path))
    assert "Shell" in {p.name for p in empty}


def test_file_at_root_is_not_a_stray(tmp_path: Path) -> None:
    empty, occupied = sweep_junk.strays(make_root(tmp_path))
    assert "README.md" not in {p.name for p in empty + occupied}


def test_dry_run_removes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_root(tmp_path)
    monkeypatch.setattr(sweep_junk, "REPO", root)
    monkeypatch.setattr(sys, "argv", ["sweep_junk.py", "--dry-run"])
    assert sweep_junk.main() == 0
    assert (root / "OF_PROCESSORS=16").is_dir()
    assert "would remove" in capsys.readouterr().out


def test_sweep_removes_only_the_empty_strays(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_root(tmp_path)
    monkeypatch.setattr(sweep_junk, "REPO", root)
    monkeypatch.setattr(sys, "argv", ["sweep_junk.py"])
    assert sweep_junk.main() == 0

    assert not (root / "OF_PROCESSORS=16").exists()
    assert not (root / "ৠ翹").exists()
    assert not (root / "Shell").exists()
    # Everything else is in place, including the foreign directory with a file.
    assert (root / "important" / "file.txt").is_file()
    assert (root / "probe-runs" / "attn" / "article.md").is_file()
    assert (root / "facet").is_dir()

    out = capsys.readouterr()
    assert "strays: 3 empty, 1 kept" in out.out
    assert "important" in out.err


def test_clean_root_is_a_no_op(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "facet").mkdir()
    monkeypatch.setattr(sweep_junk, "REPO", tmp_path)
    monkeypatch.setattr(sys, "argv", ["sweep_junk.py"])
    assert sweep_junk.main() == 0
    assert "strays: 0 empty, 0 kept" in capsys.readouterr().out


# --- junk files in the root -----------------------------------------------------------
#
# The second half of the same trouble, and it was invisible: the tool looked only at
# directories. In one working day the root collected temp_data.py, rounds_output.json,
# final_structured_output.json and rounds_structured.json, and `git add -A` put three of them
# into a commit.


def test_known_root_files_are_not_strays(tmp_path: Path) -> None:
    for name in ("pyproject.toml", "CLAUDE.md", ".gitignore"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    assert sweep_junk.stray_files(tmp_path) == []


def test_unknown_root_file_is_a_stray(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("x", encoding="utf-8")
    (tmp_path / "rounds_output.json").write_text("{}", encoding="utf-8")
    assert [p.name for p in sweep_junk.stray_files(tmp_path)] == ["rounds_output.json"]


def test_directories_are_not_counted_as_stray_files(tmp_path: Path) -> None:
    (tmp_path / "some-directory").mkdir()
    assert sweep_junk.stray_files(tmp_path) == []


def test_stray_files_are_sorted(tmp_path: Path) -> None:
    for name in ("b.json", "a.json", "c.py"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    assert [p.name for p in sweep_junk.stray_files(tmp_path)] == ["a.json", "b.json", "c.py"]


def test_without_git_a_file_counts_as_tracked(tmp_path: Path) -> None:
    """No answer means no deletion. Erasing a source file for the sake of tidiness is worse than any junk."""
    target = tmp_path / "unknown.json"
    target.write_text("{}", encoding="utf-8")
    assert sweep_junk.tracked_by_git(tmp_path, target) is True


def test_untracked_file_in_a_repo_is_removable(tmp_path: Path) -> None:
    """A clean exit code 1 from git is the only answer that allows deletion."""
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, capture_output=True)
    target = tmp_path / "draft.json"
    target.write_text("{}", encoding="utf-8")
    assert sweep_junk.tracked_by_git(tmp_path, target) is False
