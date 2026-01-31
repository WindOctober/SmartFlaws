from __future__ import annotations

import json
import random
import ssl
import time
import urllib.request
import urllib.error
from typing import Any


def _sleep_backoff(attempt: int, *, base_s: float = 0.5, max_s: float = 8.0) -> None:
    # Exponential backoff with small jitter.
    delay = min(max_s, base_s * (2**attempt))
    delay *= 1.0 + random.random() * 0.2
    time.sleep(delay)


def _urlopen_bytes(url: str, *, timeout_s: int, retries: int) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "SmartFlaws-fetcher/1.0"})
    attempts = max(1, int(retries) + 1)
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            # Retry common transient server-side issues.
            if exc.code in (429, 500, 502, 503, 504) and attempt + 1 < attempts:
                retry_after = exc.headers.get("Retry-After")
                if retry_after:
                    try:
                        time.sleep(max(0.0, float(retry_after)))
                        continue
                    except Exception:
                        pass
                _sleep_backoff(attempt)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ssl.SSLError, ConnectionResetError) as exc:
            if attempt + 1 < attempts:
                _sleep_backoff(attempt)
                continue
            raise


def http_get_json(url: str, timeout_s: int = 30, *, retries: int = 3) -> Any:
    attempts = max(1, int(retries) + 1)
    last_exc: BaseException | None = None
    for attempt in range(attempts):
        try:
            raw = _urlopen_bytes(url, timeout_s=timeout_s, retries=0)
            try:
                return json.loads(raw.decode("utf-8"))
            except Exception as exc:
                # Truncated/garbled responses happen; treat as transient.
                last_exc = RuntimeError(f"Failed to decode JSON from {url}: {exc}")
                if attempt + 1 < attempts:
                    _sleep_backoff(attempt)
                    continue
                raise last_exc
        except Exception as exc:
            last_exc = exc
            if attempt + 1 < attempts:
                _sleep_backoff(attempt)
                continue
            raise

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Unexpected http_get_json retry loop exit")


def http_get_text(url: str, timeout_s: int = 30, *, retries: int = 3) -> str:
    raw = _urlopen_bytes(url, timeout_s=timeout_s, retries=retries)
    return raw.decode("utf-8", errors="replace")


def http_post_json(url: str, payload: dict[str, Any], timeout_s: int = 30, *, retries: int = 3) -> Any:
    body = json.dumps(payload).encode("utf-8")
    attempts = max(1, int(retries) + 1)
    last_exc: BaseException | None = None
    for attempt in range(attempts):
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "User-Agent": "SmartFlaws-fetcher/1.0",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                raw = resp.read()
            try:
                return json.loads(raw.decode("utf-8"))
            except Exception as exc:
                last_exc = RuntimeError(f"Failed to decode JSON from {url}: {exc}")
                if attempt + 1 < attempts:
                    _sleep_backoff(attempt)
                    continue
                raise last_exc
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code in (429, 500, 502, 503, 504) and attempt + 1 < attempts:
                retry_after = exc.headers.get("Retry-After")
                if retry_after:
                    try:
                        time.sleep(max(0.0, float(retry_after)))
                        continue
                    except Exception:
                        pass
                _sleep_backoff(attempt)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ssl.SSLError, ConnectionResetError) as exc:
            last_exc = exc
            if attempt + 1 < attempts:
                _sleep_backoff(attempt)
                continue
            raise

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Unexpected http_post_json retry loop exit")
