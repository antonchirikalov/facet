#!/usr/bin/env python3
"""Check the figure environment before a single image is rendered, and say which critic to use.

Every item here stopped a live run without stopping it loudly:

- the Kimi critic answered 401 (expired key) or 429 (no balance) on every call, and the render
  tool printed "Critic satisfied" for images nobody had looked at;
- TMPDIR in its 8.3 form (``ACHIRI~1``) made the Claude critic refuse to read the image, so it
  judged the description instead;
- the key lived in the Windows user environment while the shell had an older copy.

So the figure stage asks first. ``--kimi`` sends one tiny image to Kimi and reports whether it
answered; the verdict ``critic`` is ``kimi`` when it did and ``claude_code`` when it did not, and
the workflow passes the critic flags only in the first case. The render tool itself also falls
back to Claude mid-run when Kimi runs out — this check only saves the first render from finding
out the hard way.

Nothing secret is printed: the key's presence and length, never its value.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

import toollog

# A 1x1 white PNG: the smallest image that still exercises the vision path.
PIXEL = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC"
)
DEFAULT_BASE = "https://api.kimi.com/coding/v1"
# The same model is called "k3" on the Kimi-for-Coding endpoint and "kimi-k3" on Moonshot.
MODEL_BY_HOST = {"api.kimi.com": "k3", "api.moonshot.ai": "kimi-k3", "api.moonshot.cn": "kimi-k3"}
SHORT_NAME = re.compile(r"(^|[\\/])[^\\/]{1,6}~\d+([\\/]|$)")

Post = Callable[[str, bytes, dict[str, str]], tuple[int, str]]


def http_post(url: str, body: bytes, headers: dict[str, str]) -> tuple[int, str]:
    request = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError) as e:
        return 0, str(e)


def model_for(base: str) -> str:
    host = re.sub(r"^https?://", "", base).split("/")[0]
    return MODEL_BY_HOST.get(host, "k3")


def check_kimi(key: str | None, base: str, model: str | None, post: Post) -> dict[str, Any]:
    """One vision call. Returns status, a short reason, and whether the critic can be used."""
    if not key:
        return {"usable": False, "status": None, "reason": "MOONSHOT_API_KEY is not set"}
    model = model or model_for(base)
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{PIXEL}"},
                        },
                        {"type": "text", "text": "Reply with the single word OK."},
                    ],
                }
            ],
        }
    ).encode()
    status, text = post(
        base.rstrip("/") + "/chat/completions",
        body,
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    if status == 200:
        return {"usable": True, "status": 200, "reason": f"{model} answered"}
    try:
        message = json.loads(text).get("error", {}).get("message", text)
    except (ValueError, AttributeError):
        message = text
    return {"usable": False, "status": status, "reason": str(message)[:200], "model": model}


def check_tmpdir(env: dict[str, str]) -> list[str]:
    problems = []
    for name in ("TMPDIR", "TEMP", "TMP"):
        value = env.get(name, "")
        if value and SHORT_NAME.search(value):
            problems.append(
                f"{name} is an 8.3 short path ({value}); the vision critic cannot read images "
                f"there — point it at a long path inside the run directory"
            )
    return problems


def registry_key() -> str | None:
    """The user-level Windows value, which a long-running session does not see change.

    A Claude Code session keeps the environment it started with. On 28.09 the key was replaced
    in the user environment while the session still carried the old one: every call from it got
    401, while the same call with the registry value answered. So the registry is asked too.
    """
    if sys.platform != "win32":
        return None
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            value, _ = winreg.QueryValueEx(k, "MOONSHOT_API_KEY")
            return str(value) or None
    except OSError:
        return None


def preflight(
    env: dict[str, str],
    kimi: bool,
    post: Post = http_post,
    fresh_key: Callable[[], str | None] | None = None,
) -> dict[str, Any]:
    problems = check_tmpdir(env)
    key = env.get("MOONSHOT_API_KEY")
    measures: dict[str, Any] = {"moonshot_key": f"set, {len(key)} chars" if key else "missing"}
    critic = "claude_code"
    if kimi:
        base = env.get("KIMI_BASE_URL") or DEFAULT_BASE
        model = env.get("KIMI_CRITIC_MODEL")
        result = check_kimi(key, base, model, post)
        if not result["usable"]:
            newer = (fresh_key or registry_key)()
            if newer and newer != key:
                retry = check_kimi(newer, base, model, post)
                if retry["usable"]:
                    result = {
                        **retry,
                        "reason": retry["reason"] + "; the session's key is stale, the user "
                        "environment has a working one — export it before rendering",
                        "stale_session_key": True,
                    }
        measures["kimi"] = {"base": base, **result}
        if result["usable"]:
            critic = "kimi"
    return {
        # TMPDIR problems fail the check; an unusable Kimi does not, because Claude takes over.
        "ok": not problems,
        "problems": problems,
        "measures": measures,
        "critic": critic,
        "critic_model": (measures.get("kimi") or {}).get("model")
        or model_for(env.get("KIMI_BASE_URL") or DEFAULT_BASE)
        if critic == "kimi"
        else "sonnet",
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Check the figure environment; choose the critic.")
    p.add_argument("--kimi", action="store_true", help="probe the Kimi critic with one image")
    toollog.add_argument(p)
    args = p.parse_args()
    report = preflight(dict(os.environ), args.kimi)
    toollog.append(args.log, "preflight", report, args.log_note, release=args.log_release)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
