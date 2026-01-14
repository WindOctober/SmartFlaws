from __future__ import annotations

import time
from typing import Any

from .explorer import scan_url
from .http import http_get_json
from .rpc import rpc_get_logs
from .util import normalize_address


def decode_topic_address(topic_hex: str) -> str:
    s = (topic_hex or "").strip().lower()
    if not s.startswith("0x"):
        raise ValueError(f"Bad topic: {topic_hex!r}")
    addr = "0x" + s[-40:]
    return normalize_address(addr)


def decode_data_word_address(data_hex: str, word_index: int) -> str:
    s = (data_hex or "").strip().lower()
    if not s.startswith("0x"):
        raise ValueError(f"Bad data: {data_hex!r}")
    body = s[2:]
    start = word_index * 64
    end = start + 64
    if len(body) < end:
        raise ValueError(f"Data too short for word {word_index}: {data_hex!r}")
    word = body[start:end]
    addr = "0x" + word[-40:]
    return normalize_address(addr)


def scan_get_logs_explorer(
    api_base: str,
    api_key: str,
    address: str,
    from_block: int,
    to_block: int,
    topic0: str,
    *,
    chainid: int | None = None,
    timeout_s: int = 30,
) -> list[dict[str, Any]]:
    url = scan_url(
        api_base,
        api_key,
        chainid=chainid,
        module="logs",
        action="getLogs",
        address=address,
        fromBlock=str(from_block),
        toBlock=str(to_block),
        topic0=topic0,
    )
    data = http_get_json(url, timeout_s=timeout_s)
    if not isinstance(data, dict):
        raise RuntimeError(f"Unexpected getLogs response: {data!r}")
    result = data.get("result")
    if isinstance(result, list):
        return [r for r in result if isinstance(r, dict)]
    return []


def iter_pairs_from_factory_rpc(
    factory_address: str,
    from_block: int,
    to_block: int,
    *,
    rpc_url: str,
    topic0: str,
    chunk_blocks: int = 50_000,
    sleep_s: float = 0.25,
    token0_filter: str | None = None,
    token1_filter: str | None = None,
    token0_topic_index: int = 1,
    token1_topic_index: int = 2,
    pair_data_word: int = 0,
    max_pairs: int = 0,
) -> list[tuple[str, str, str]]:
    factory = normalize_address(factory_address)
    if chunk_blocks <= 0:
        raise ValueError("chunk_blocks must be > 0")
    if token0_topic_index < 0 or token1_topic_index < 0:
        raise ValueError("token topic indexes must be >= 0")
    if pair_data_word < 0:
        raise ValueError("pair_data_word must be >= 0")

    tok0 = normalize_address(token0_filter) if token0_filter else None
    tok1 = normalize_address(token1_filter) if token1_filter else None

    out: list[tuple[str, str, str]] = []
    cur = int(from_block)
    end = int(to_block)
    adaptive_chunk = int(chunk_blocks)
    while cur <= end:
        hi = min(end, cur + adaptive_chunk - 1)
        try:
            logs = rpc_get_logs(rpc_url, factory, cur, hi, topics=[topic0])
        except RuntimeError as exc:
            msg = str(exc).lower()
            if adaptive_chunk > 1 and ("range" in msg or "limit" in msg or "too large" in msg or "exceeded" in msg):
                adaptive_chunk = max(1, adaptive_chunk // 2)
                continue
            raise
        for log in logs:
            topics = log.get("topics")
            data = log.get("data")
            if not isinstance(topics, list) or len(topics) <= max(token0_topic_index, token1_topic_index) or not isinstance(data, str):
                continue
            try:
                t0 = decode_topic_address(str(topics[token0_topic_index]))
                t1 = decode_topic_address(str(topics[token1_topic_index]))
                pair = decode_data_word_address(data, pair_data_word)
            except Exception:
                continue
            if tok0 and t0 != tok0:
                continue
            if tok1 and t1 != tok1:
                continue
            out.append((pair, t0, t1))
            if max_pairs and len(out) >= max_pairs:
                return out
        time.sleep(sleep_s)
        cur = hi + 1
    return out


def iter_pairs_from_factory_explorer(
    api_base: str,
    api_key: str,
    factory_address: str,
    from_block: int,
    to_block: int,
    *,
    chainid: int | None = None,
    topic0: str,
    chunk_blocks: int = 50_000,
    sleep_s: float = 0.25,
    token0_filter: str | None = None,
    token1_filter: str | None = None,
    token0_topic_index: int = 1,
    token1_topic_index: int = 2,
    pair_data_word: int = 0,
    max_pairs: int = 0,
) -> list[tuple[str, str, str]]:
    factory = normalize_address(factory_address)
    if chunk_blocks <= 0:
        raise ValueError("chunk_blocks must be > 0")

    tok0 = normalize_address(token0_filter) if token0_filter else None
    tok1 = normalize_address(token1_filter) if token1_filter else None

    out: list[tuple[str, str, str]] = []
    cur = int(from_block)
    end = int(to_block)
    while cur <= end:
        hi = min(end, cur + chunk_blocks - 1)
        logs = scan_get_logs_explorer(
            api_base,
            api_key,
            factory,
            cur,
            hi,
            topic0=topic0,
            chainid=chainid,
        )
        for log in logs:
            topics = log.get("topics")
            data = log.get("data")
            if not isinstance(topics, list) or len(topics) <= max(token0_topic_index, token1_topic_index) or not isinstance(data, str):
                continue
            try:
                t0 = decode_topic_address(str(topics[token0_topic_index]))
                t1 = decode_topic_address(str(topics[token1_topic_index]))
                pair = decode_data_word_address(data, pair_data_word)
            except Exception:
                continue
            if tok0 and t0 != tok0:
                continue
            if tok1 and t1 != tok1:
                continue
            out.append((pair, t0, t1))
            if max_pairs and len(out) >= max_pairs:
                return out
        time.sleep(sleep_s)
        cur = hi + 1
    return out

