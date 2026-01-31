from __future__ import annotations

import random
import time
from typing import Any

from .http import http_post_json
from .util import normalize_address


def _sleep_backoff(attempt: int, *, base_s: float = 0.5, max_s: float = 8.0) -> None:
    delay = min(max_s, base_s * (2**attempt))
    delay *= 1.0 + random.random() * 0.2
    time.sleep(delay)


def _is_transient_rpc_error(error_obj: Any) -> bool:
    if isinstance(error_obj, dict):
        code = error_obj.get("code")
        msg = str(error_obj.get("message") or "").lower()
        # Common transient JSON-RPC provider codes/messages.
        if code in (-32005, -32000, -32603):
            return True
        if any(
            k in msg
            for k in (
                "rate limit",
                "too many requests",
                "exceeded",
                "limit",
                "timeout",
                "timed out",
                "temporarily unavailable",
                "service unavailable",
                "try again",
                "busy",
                "gateway",
                "internal error",
                "upstream",
            )
        ):
            return True
        return False
    # Fallback: treat unknown-shaped errors as non-transient.
    return False


def rpc_call(rpc_url: str, method: str, params: list[Any], *, retries: int = 3) -> Any:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    attempts = max(1, int(retries) + 1)
    last_exc: BaseException | None = None
    for attempt in range(attempts):
        try:
            resp = http_post_json(rpc_url, payload)
            if not isinstance(resp, dict):
                raise RuntimeError(f"Unexpected RPC response: {resp!r}")
            if "error" in resp and resp["error"]:
                err = resp["error"]
                if _is_transient_rpc_error(err) and attempt + 1 < attempts:
                    _sleep_backoff(attempt)
                    continue
                raise RuntimeError(f"RPC error for {method}: {err!r}")
            return resp.get("result")
        except Exception as exc:
            last_exc = exc
            msg = str(exc).lower()
            # http.py already retries common network errors; this is a second chance for
            # providers that return valid JSON-RPC errors for transient conditions.
            if attempt + 1 < attempts and any(
                k in msg
                for k in (
                    "rate limit",
                    "too many requests",
                    "timed out",
                    "timeout",
                    "temporarily unavailable",
                    "service unavailable",
                    "connection reset",
                    "remote end closed connection",
                )
            ):
                _sleep_backoff(attempt)
                continue
            raise

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Unexpected rpc_call retry loop exit")


def rpc_block_number(rpc_url: str) -> int:
    res = rpc_call(rpc_url, "eth_blockNumber", [])
    if not isinstance(res, str) or not res.startswith("0x"):
        raise RuntimeError(f"Unexpected eth_blockNumber result: {res!r}")
    return int(res, 16)


def rpc_eth_call(rpc_url: str, to: str, data: str, tag: str = "latest") -> str:
    params: list[Any] = [
        {
            "to": normalize_address(to),
            "data": data,
        },
        tag,
    ]
    res = rpc_call(rpc_url, "eth_call", params)
    if not isinstance(res, str):
        raise RuntimeError(f"Unexpected eth_call result: {res!r}")
    return res


def rpc_get_logs(
    rpc_url: str,
    address: str,
    from_block: int,
    to_block: int,
    topics: list[str | None],
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "fromBlock": hex(int(from_block)),
        "toBlock": hex(int(to_block)),
        "address": normalize_address(address),
        "topics": topics,
    }
    res = rpc_call(rpc_url, "eth_getLogs", [params])
    if isinstance(res, list):
        return [r for r in res if isinstance(r, dict)]
    return []
