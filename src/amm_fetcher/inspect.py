from __future__ import annotations

from .constants import BALANCEOF_SELECTOR, GETRESERVES_SELECTOR, TOKEN0_SELECTOR, TOKEN1_SELECTOR
from .rpc import rpc_eth_call
from .util import decode_eth_call_address, decode_eth_call_uint, eth_call_data_with_address


def rpc_detect_pair_tokens(rpc_url: str, pair_address: str) -> tuple[str, str] | None:
    try:
        token0_hex = rpc_eth_call(rpc_url, pair_address, TOKEN0_SELECTOR)
        token1_hex = rpc_eth_call(rpc_url, pair_address, TOKEN1_SELECTOR)
        token0 = decode_eth_call_address(token0_hex)
        token1 = decode_eth_call_address(token1_hex)
    except Exception:
        return None
    if token0 == "0x0000000000000000000000000000000000000000":
        return None
    if token1 == "0x0000000000000000000000000000000000000000":
        return None
    if token0 == token1:
        return None
    return (token0, token1)


def rpc_get_reserves(rpc_url: str, pair_address: str) -> tuple[int, int, int] | None:
    """
    Decode getReserves() -> (uint112 reserve0, uint112 reserve1, uint32 blockTimestampLast)
    """
    try:
        out = rpc_eth_call(rpc_url, pair_address, GETRESERVES_SELECTOR)
        s = out.strip().lower()
        if not s.startswith("0x"):
            return None
        body = s[2:]
        if len(body) < 64 * 3:
            return None
        r0 = int(body[0:64], 16)
        r1 = int(body[64:128], 16)
        ts = int(body[128:192], 16)
        return (r0, r1, ts)
    except Exception:
        return None


def rpc_erc20_balance_of(rpc_url: str, token: str, owner: str) -> int | None:
    try:
        data = eth_call_data_with_address(BALANCEOF_SELECTOR, owner)
        out = rpc_eth_call(rpc_url, token, data)
        return decode_eth_call_uint(out)
    except Exception:
        return None

