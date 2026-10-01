"""Tests for the preflight of the figures stage: which critic is available and whether TMPDIR is broken.

All cases come from one live run: the Kimi key expired (401), the balance ran out (429), and a
TMPDIR with an 8.3 name blinded the critic. The tests need no network: the request is stubbed.
"""

from __future__ import annotations

import json

import preflight
import pytest


@pytest.fixture(autouse=True)
def no_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real user environment is never read in a test."""
    monkeypatch.setattr(preflight, "registry_key", lambda: None)


def post_returning(status: int, text: str = "{}") -> preflight.Post:
    calls: list[str] = []

    def post(url: str, body: bytes, headers: dict[str, str]) -> tuple[int, str]:
        calls.append(json.loads(body)["model"])
        return status, text

    post.calls = calls  # type: ignore[attr-defined]
    return post


def test_working_kimi_is_chosen() -> None:
    post = post_returning(200)
    report = preflight.preflight({"MOONSHOT_API_KEY": "k" * 51}, kimi=True, post=post)
    assert report["critic"] == "kimi" and report["critic_model"] == "k3"
    assert report["ok"] is True


def test_expired_key_falls_back_to_claude_without_failing() -> None:
    body = '{"error": {"message": "The API Key appears to be invalid or may have expired."}}'
    report = preflight.preflight(
        {"MOONSHOT_API_KEY": "k" * 51}, kimi=True, post=post_returning(401, body)
    )
    assert report["critic"] == "claude_code" and report["critic_model"] == "sonnet"
    assert report["ok"] is True
    assert "expired" in report["measures"]["kimi"]["reason"]


def test_no_balance_falls_back() -> None:
    report = preflight.preflight(
        {"MOONSHOT_API_KEY": "k", "KIMI_BASE_URL": "https://api.moonshot.ai/v1"},
        kimi=True,
        post=post_returning(429, '{"error": {"message": "suspended due to insufficient balance"}}'),
    )
    assert report["critic"] == "claude_code"
    assert report["measures"]["kimi"]["model"] == "kimi-k3"


def test_missing_key_is_reported_not_raised() -> None:
    report = preflight.preflight({}, kimi=True, post=post_returning(200))
    assert report["critic"] == "claude_code"
    assert report["measures"]["moonshot_key"] == "missing"


def test_key_value_never_printed() -> None:
    report = preflight.preflight(
        {"MOONSHOT_API_KEY": "secret-value-123"}, kimi=True, post=post_returning(200)
    )
    assert "secret-value-123" not in json.dumps(report)


def test_short_tmpdir_fails_the_check() -> None:
    report = preflight.preflight({"TMPDIR": r"C:\Users\ACHIRI~1\AppData\Local\Temp"}, kimi=False)
    assert report["ok"] is False and "8.3" in report["problems"][0]


def test_long_tmpdir_passes() -> None:
    report = preflight.preflight({"TMPDIR": "C:/Users/achirikalov/work/tmp"}, kimi=False)
    assert report["ok"] is True and report["problems"] == []


def test_stale_session_key_is_replaced_by_the_user_environment() -> None:
    def post(url: str, body: bytes, headers: dict[str, str]) -> tuple[int, str]:
        return (200, "{}") if headers["Authorization"].endswith("new") else (401, "{}")

    report = preflight.preflight(
        {"MOONSHOT_API_KEY": "old"}, kimi=True, post=post, fresh_key=lambda: "new"
    )
    assert report["critic"] == "kimi"
    assert report["measures"]["kimi"]["stale_session_key"] is True


def test_no_fresh_key_keeps_claude() -> None:
    report = preflight.preflight(
        {"MOONSHOT_API_KEY": "old"}, kimi=True, post=post_returning(401), fresh_key=lambda: None
    )
    assert report["critic"] == "claude_code"
