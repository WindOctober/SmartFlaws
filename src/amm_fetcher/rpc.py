from __future__ import annotations

from typing import Any

from .http import http_post_json
from .util import normalize_address


def rpc_call(rpc_url: str, method: str, params: list[Any]) -> Any:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    resp = http_post_json(rpc_url, payload)
    if not isinstance(resp, dict):
        raise RuntimeError(f"Unexpected RPC response: {resp!r}")
    if "error" in resp and resp["error"]:
        raise RuntimeError(f"RPC error for {method}: {resp['error']!r}")
    return resp.get("result")


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

