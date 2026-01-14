from __future__ import annotations

import json
import urllib.request
from typing import Any


def http_get_json(url: str, timeout_s: int = 30) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "SmartFlaws-fetcher/1.0"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read()
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Failed to decode JSON from {url}: {exc}") from exc


def http_post_json(url: str, payload: dict[str, Any], timeout_s: int = 30) -> Any:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "User-Agent": "SmartFlaws-fetcher/1.0",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read()
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Failed to decode JSON from {url}: {exc}") from exc

