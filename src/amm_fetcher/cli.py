from __future__ import annotations

import argparse
import json
import os
import sys
import time
import shutil
from pathlib import Path
from typing import Any

from .constants import (
    BALANCEOF_SELECTOR,
    ETHERSCAN_V2_API_BASE,
    GETRESERVES_SELECTOR,
    PAIRCREATED_TOPIC0,
    TOKEN0_SELECTOR,
    TOKEN1_SELECTOR,
)
from .discovery import iter_pairs_from_factory_explorer, iter_pairs_from_factory_rpc
from .explorer import classify_verified_from_getsourcecode_response, get_sourcecode
from .inspect import rpc_detect_pair_tokens
from .rpc import rpc_block_number, rpc_eth_call
from .util import (
    color_path,
    decode_eth_call_address,
    decode_eth_call_uint,
    eth_call_data_with_address,
    load_api_key,
    normalize_address,
    read_addresses_file,
    write_json,
    write_sources,
)
from .types import VerifiedContract
from .explorer import load_verified_contract


def dump_contract(out_dir: Path, kind: str, contract: VerifiedContract) -> None:
    meta = {
        "kind": kind,
        "address": contract.address,
        "contractName": contract.contract_name,
        "language": contract.language,
        "compilerVersion": contract.compiler_version,
    }
    write_json(out_dir / "metadata.json", meta)
    write_json(out_dir / "abi.json", contract.abi)
    write_json(out_dir / "bscscan_record.json", contract.raw_record)
    write_sources(out_dir / "source", contract.sources)


def _fmt_duration_s(seconds: float) -> str:
    s = max(0, int(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


def _short_addr(addr: str, *, head: int = 6, tail: int = 4) -> str:
    a = (addr or "").strip()
    if len(a) <= head + tail + 3:
        return a
    return f"{a[:head]}…{a[-tail:]}"


class _Progress:
    def __init__(self, label: str, total: int, *, enabled: bool, every: int) -> None:
        self.label = label
        self.total = max(0, int(total))
        self.enabled = bool(enabled) and self.total > 0
        self.every = max(1, int(every))
        self.start_s = time.time()
        self.is_tty = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()
        self.last_done = 0
        self.last_current = ""
        self.use_color = self.is_tty and (os.environ.get("NO_COLOR") is None) and ((os.environ.get("TERM") or "").lower() not in ("", "dumb"))

    def _clear_line(self) -> None:
        if not (self.enabled and self.is_tty):
            return
        sys.stderr.write("\r\x1b[2K")
        sys.stderr.flush()

    def _c(self, s: str, code: str) -> str:
        if not self.use_color:
            return s
        return f"\x1b[{code}m{s}\x1b[0m"

    def _render_line(self, n_done: int, *, current: str) -> str:
        width = shutil.get_terminal_size(fallback=(100, 24)).columns
        now_s = time.time()
        elapsed = now_s - self.start_s
        rate = (n_done / elapsed) if elapsed > 0 else 0.0
        remaining = self.total - n_done
        eta = (remaining / rate) if rate > 0 else 0.0
        pct = (100.0 * n_done / self.total) if self.total else 100.0

        if width < 22:
            prefix = self.label[:1]
        elif width < 30:
            prefix = self.label
        else:
            prefix = f"[{self.label}]"
        count_plain = f"{n_done}/{self.total}"
        pct_plain = f"{pct:5.1f}%"
        elapsed_plain = f"elapsed={_fmt_duration_s(elapsed)}"
        eta_plain = f"eta={_fmt_duration_s(eta)}"
        rate_plain = f"rate={rate:4.1f}/s"

        suffix_fields: list[str] = [pct_plain, count_plain, elapsed_plain]
        if width >= 80:
            suffix_fields.append(eta_plain)
        if width >= 95:
            suffix_fields.append(rate_plain)

        # Make sure the line never wraps: shrink suffix then bar to fit.
        def compute_available() -> tuple[str, int]:
            suffix_p = " ".join(suffix_fields)
            reserved = len(prefix) + 4 + len(suffix_p)  # prefix + space + [ ] + space + suffix
            return suffix_p, width - reserved

        suffix_plain, available = compute_available()
        while available < 5 and len(suffix_fields) > 2:
            suffix_fields.pop()
            suffix_plain, available = compute_available()

        # Last resort: if still too small, keep only the essentials.
        if available < 3 and len(suffix_fields) > 1:
            suffix_fields = [pct_plain, count_plain] if width >= 18 else [count_plain]
            suffix_plain, available = compute_available()

        suffix = suffix_plain.replace(count_plain, self._c(count_plain, "1;33"))
        bar_w = max(1, min(40, available))

        # Render bar as ====> style.
        fill = int(round((pct / 100.0) * bar_w))
        fill = max(0, min(bar_w, fill))
        if fill <= 0:
            bar = " " * bar_w
        elif fill >= bar_w:
            bar = "=" * (bar_w - 1) + ">"
        else:
            bar = "=" * max(0, fill - 1) + ">" + " " * (bar_w - fill)

        bar_colored = self._c(bar, "1;36")
        return f"{prefix} [{bar_colored}] {suffix}"

    def update(self, n_done: int, *, current: str = "", force: bool = False) -> None:
        if not self.enabled:
            return
        self.last_done = int(n_done)
        self.last_current = str(current or "")
        if not force and n_done != self.total and (n_done % self.every) != 0 and n_done != 1:
            return

        if self.is_tty:
            self._clear_line()
            sys.stderr.write(self._render_line(n_done, current=current))
            sys.stderr.flush()
            return
        sys.stderr.write(self._render_line(n_done, current=current) + "\n")
        sys.stderr.flush()

    def log(self, msg: str, *, stream: Any = None) -> None:
        out = stream if stream is not None else sys.stderr
        if self.enabled and self.is_tty:
            self._clear_line()
            print(msg, file=out, flush=True)
            self.update(self.last_done, current=self.last_current, force=True)
        else:
            print(msg, file=out, flush=True)

    def done(self) -> None:
        if self.enabled and self.is_tty:
            sys.stderr.write("\n")
            sys.stderr.flush()


def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    cleaned: list[tuple[int, int]] = []
    for lo, hi in sorted(intervals):
        if hi < lo:
            continue
        if not cleaned:
            cleaned.append((lo, hi))
            continue
        prev_lo, prev_hi = cleaned[-1]
        if lo <= prev_hi + 1:
            cleaned[-1] = (prev_lo, max(prev_hi, hi))
        else:
            cleaned.append((lo, hi))
    return cleaned


def _subtract_intervals(target: tuple[int, int], covered: list[tuple[int, int]]) -> list[tuple[int, int]]:
    lo, hi = target
    if hi < lo:
        return []
    remaining: list[tuple[int, int]] = [(lo, hi)]
    for c_lo, c_hi in covered:
        next_remaining: list[tuple[int, int]] = []
        for r_lo, r_hi in remaining:
            if c_hi < r_lo or c_lo > r_hi:
                next_remaining.append((r_lo, r_hi))
                continue
            if r_lo < c_lo:
                next_remaining.append((r_lo, c_lo - 1))
            if c_hi < r_hi:
                next_remaining.append((c_hi + 1, r_hi))
        remaining = next_remaining
        if not remaining:
            break
    return remaining


def _cache_key_for_discovery(args: argparse.Namespace, *, chainid: int | None) -> str:
    parts = [
        f"chainid={chainid or 0}",
        f"factory={str(args.factory).lower()}",
        f"topic0={str(args.topic0).lower()}",
        f"pair_data_word={int(args.pair_data_word)}",
        f"token0={str(args.token0 or '').lower()}",
        f"token1={str(args.token1 or '').lower()}",
    ]
    return "_".join(parts).replace("/", "_")


def _cache_key_for_inspect(args: argparse.Namespace, *, chainid: int | None, pairs_file: str) -> str:
    base = f"chainid={chainid or 0}"
    pf = (pairs_file or "").strip().replace("/", "_")
    if not pf:
        pf = "inline"
    return f"{base}_pairsfile={pf}"


def _load_json_if_exists(path: Path) -> Any | None:
    try:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _is_complete_inspect_row(row: dict[str, Any]) -> bool:
    if row.get("token0") is None or row.get("token1") is None:
        return False
    if row.get("reserve0") is None or row.get("reserve1") is None or row.get("blockTimestampLast") is None:
        return False
    if row.get("balance0") is None or row.get("balance1") is None:
        return False
    return True


def main(argv: list[str]) -> int:
    if argv and argv[0] in {"discover", "inspect", "fetch", "parse"}:
        return _main_subcommand(argv)

    p = argparse.ArgumentParser(
        description="Fetch verified AMM (pair-style) contracts + their verified token contracts (Etherscan API v2 + RPC).",
    )
    p.add_argument(
        "addresses",
        nargs="*",
        help="Candidate AMM contract addresses (pair-style, e.g. UniswapV2 pair).",
    )
    p.add_argument(
        "--factory",
        help="Factory address to scan PairCreated logs (UniswapV2/Pancake-style).",
    )
    p.add_argument(
        "--from-block",
        type=int,
        default=0,
        help="Start block when scanning --factory.",
    )
    p.add_argument(
        "--to-block",
        type=int,
        default=0,
        help="End block when scanning --factory (0 means latest).",
    )
    p.add_argument(
        "--latest-blocks",
        type=int,
        default=0,
        help="Scan only the latest N blocks when using --factory (overrides --from-block/--to-block).",
    )
    p.add_argument(
        "--chunk-blocks",
        type=int,
        default=50_000,
        help="Block chunk size for factory log scans (RPC will auto-shrink on provider limits).",
    )
    p.add_argument(
        "--token0",
        default="",
        help="Optional token0 filter when scanning --factory.",
    )
    p.add_argument(
        "--token1",
        default="",
        help="Optional token1 filter when scanning --factory.",
    )
    p.add_argument(
        "--topic0",
        default=PAIRCREATED_TOPIC0,
        help="Event signature topic0 to scan (defaults to UniswapV2 PairCreated).",
    )
    p.add_argument(
        "--pair-data-word",
        type=int,
        default=0,
        help="Which 32-byte data word contains the created pair address (default 0).",
    )
    p.add_argument(
        "--max-pairs",
        type=int,
        default=0,
        help="Stop scanning a factory after discovering N pairs (0 means no limit).",
    )
    p.add_argument(
        "--discover-only",
        action="store_true",
        help="Only discover pair addresses (via --factory) and print them; skip fetching verified sources.",
    )
    p.add_argument(
        "--inspect-pairs",
        action="store_true",
        help="Inspect pairs: fetch token0/token1, reserves, balances via --rpc-url; optionally check verified via explorer.",
    )
    p.add_argument(
        "--verified-only",
        action="store_true",
        help="Fetch verified sources for the provided addresses only (no AMM token0/token1 detection; --rpc-url not required).",
    )
    p.add_argument(
        "--pairs-file",
        default="",
        help="Read pair addresses from a file (one per line, or output of --discover-only).",
    )
    p.add_argument(
        "--report-json",
        default="",
        help="Write inspection results to this JSON file (default: output/inspect_pairs_report.json; use '-' to print JSON to stdout).",
    )
    p.add_argument(
        "--progress-every",
        type=int,
        default=1,
        help="Print progress every N pairs during inspection/fetch (default: 1).",
    )
    p.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable progress output (useful for CI/logs).",
    )
    p.add_argument(
        "--output-dir",
        default="output",
        help="Local output/cache directory (default: output/; gitignored).",
    )
    p.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable local caching (always recompute).",
    )
    p.add_argument(
        "--pair-retries",
        type=int,
        default=2,
        help="Retry incomplete pair inspections N times (default: 2).",
    )
    p.add_argument(
        "--api-key-path",
        default="",
        help="Optional path to an Etherscan API key file (also accepts env ETHERSCAN_API_KEY).",
    )
    p.add_argument(
        "--results-dir",
        default="results",
        help="Output directory (will be gitignored).",
    )
    p.add_argument(
        "--sleep-ms",
        type=int,
        default=250,
        help="Sleep between explorer API requests to reduce rate-limiting.",
    )
    p.add_argument(
        "--api-base",
        default=ETHERSCAN_V2_API_BASE,
        help="Etherscan-compatible API base URL (recommended: https://api.etherscan.io/v2/api).",
    )
    p.add_argument(
        "--chainid",
        type=int,
        default=0,
        help="Chain id for Etherscan API v2 (e.g. 56 for BSC, 137 for Polygon).",
    )
    p.add_argument(
        "--rpc-url",
        default="",
        help="Optional JSON-RPC URL; if set, factory scanning uses eth_getLogs instead of explorer getLogs.",
    )
    args = p.parse_args(argv)

    rpc_url = str(args.rpc_url).strip()
    discover_only = bool(args.discover_only)

    api_base = str(args.api_base).strip() or ETHERSCAN_V2_API_BASE
    chainid = int(args.chainid) if int(args.chainid) > 0 else None
    requires_chainid = api_base == ETHERSCAN_V2_API_BASE

    output_root = Path(args.output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    sleep_s = max(0, args.sleep_ms) / 1000.0

    addr_list: list[str] = []
    if args.pairs_file:
        addr_list.extend(read_addresses_file(args.pairs_file))

    # Factory discovery (RPC preferred).
    if args.factory:
        if not rpc_url and not args.api_key_path:
            raise SystemExit("--factory requires --rpc-url or an explorer API key")
        latest = rpc_block_number(rpc_url) if rpc_url else 0
        api_key = ""
        if not rpc_url:
            if requires_chainid and chainid is None:
                raise SystemExit("--chainid is required when using the Etherscan API v2 base")
            api_key = load_api_key(Path(args.api_key_path) if args.api_key_path else None)
            # best-effort: without RPC we can't resolve latest block; require explicit to_block
            if int(args.to_block) <= 0 and int(args.latest_blocks) <= 0:
                raise SystemExit("--to-block is required for explorer-based factory scans (or provide --rpc-url)")

        if rpc_url:
            latest = rpc_block_number(rpc_url)

        if args.latest_blocks:
            if args.latest_blocks < 0:
                raise SystemExit("--latest-blocks must be >= 0")
            from_block = max(0, latest - int(args.latest_blocks) + 1)
            to_block = latest
        else:
            from_block = int(args.from_block)
            to_block = latest if rpc_url and int(args.to_block) == 0 else int(args.to_block)

        # Cache discovery by block range so reruns can skip already-scanned intervals.
        cache_enabled = not args.no_cache
        discovery_key = _cache_key_for_discovery(args, chainid=chainid)
        discovery_cache_path = output_root / "cache" / "discovery" / f"{discovery_key}.json"
        discovery_cache = _load_json_if_exists(discovery_cache_path) if cache_enabled else None
        covered_intervals: list[tuple[int, int]] = []
        cached_pairs: list[tuple[str, str, str]] = []
        if isinstance(discovery_cache, dict):
            raw_intervals = discovery_cache.get("covered_intervals")
            if isinstance(raw_intervals, list):
                for it in raw_intervals:
                    if isinstance(it, list) and len(it) == 2:
                        try:
                            covered_intervals.append((int(it[0]), int(it[1])))
                        except Exception:
                            continue
            raw_pairs = discovery_cache.get("pairs")
            if isinstance(raw_pairs, list):
                for it in raw_pairs:
                    if isinstance(it, list) and len(it) == 3:
                        cached_pairs.append((str(it[0]), str(it[1]), str(it[2])))
        covered_intervals = _merge_intervals(covered_intervals)
        missing = _subtract_intervals((from_block, to_block), covered_intervals) if cache_enabled else [(from_block, to_block)]
        pairs: list[tuple[str, str, str]] = []
        if cached_pairs:
            pairs.extend(cached_pairs)

        for seg_lo, seg_hi in missing:
            if rpc_url:
                seg_pairs = iter_pairs_from_factory_rpc(
                    args.factory,
                    seg_lo,
                    seg_hi,
                    rpc_url=rpc_url,
                    topic0=args.topic0,
                    chunk_blocks=args.chunk_blocks,
                    sleep_s=sleep_s,
                    token0_filter=args.token0 or None,
                    token1_filter=args.token1 or None,
                    pair_data_word=args.pair_data_word,
                    max_pairs=args.max_pairs,
                )
            else:
                seg_pairs = iter_pairs_from_factory_explorer(
                    api_base,
                    api_key,
                    args.factory,
                    seg_lo,
                    seg_hi,
                    chainid=chainid,
                    topic0=args.topic0,
                    chunk_blocks=args.chunk_blocks,
                    sleep_s=sleep_s,
                    token0_filter=args.token0 or None,
                    token1_filter=args.token1 or None,
                    pair_data_word=args.pair_data_word,
                    max_pairs=args.max_pairs,
                )
            pairs.extend(seg_pairs)
            if cache_enabled:
                covered_intervals.append((seg_lo, seg_hi))

        # Deduplicate pairs by address.
        seen_pairs: set[str] = set()
        deduped: list[tuple[str, str, str]] = []
        for pair, t0, t1 in pairs:
            paddr = str(pair).lower()
            if paddr in seen_pairs:
                continue
            seen_pairs.add(paddr)
            deduped.append((pair, t0, t1))
        pairs = deduped

        if cache_enabled:
            discovery_cache_out = {
                "meta": {
                    "created_at": int(time.time()),
                    "chainid": chainid or 0,
                    "factory": str(args.factory),
                    "topic0": str(args.topic0),
                    "pair_data_word": int(args.pair_data_word),
                    "token0_filter": str(args.token0 or ""),
                    "token1_filter": str(args.token1 or ""),
                },
                "covered_intervals": _merge_intervals(covered_intervals),
                "pairs": pairs,
            }
            _write_json_atomic(discovery_cache_path, discovery_cache_out)

        for pair, t0, t1 in pairs:
            print(f"[+] discovered pair: {pair} (token0={t0}, token1={t1})")
            addr_list.append(pair)

    addr_list.extend(args.addresses or [])

    if discover_only:
        for raw in args.addresses or []:
            try:
                pair_address = normalize_address(raw)
            except ValueError:
                continue
            print(f"[+] candidate: {pair_address}")
        return 0
    if args.inspect_pairs:
        if not rpc_url:
            raise SystemExit("--inspect-pairs requires --rpc-url")
        if requires_chainid and chainid is None:
            raise SystemExit("--chainid is required when using the Etherscan API v2 base")
        explorer_key = ""
        try:
            explorer_key = load_api_key(Path(args.api_key_path) if args.api_key_path else None)
        except SystemExit:
            explorer_key = ""

        progress = _Progress(
            "inspect",
            len(addr_list),
            enabled=not args.no_progress,
            every=args.progress_every,
        )
        null_reason_counts: dict[str, int] = {}
        error_type_counts: dict[str, int] = {}

        def add_null_reason(reason: str) -> None:
            null_reason_counts[reason] = null_reason_counts.get(reason, 0) + 1

        def add_error_type(kind: str, exc: BaseException) -> str:
            label = f"{kind}:{type(exc).__name__}"
            error_type_counts[label] = error_type_counts.get(label, 0) + 1
            return f"{type(exc).__name__}: {exc}"

        cache_enabled = not args.no_cache
        inspect_key = _cache_key_for_inspect(args, chainid=chainid, pairs_file=str(args.pairs_file or ""))
        inspect_cache_dir = output_root / "cache" / "inspect" / inspect_key
        inspect_pairs_cache_dir = inspect_cache_dir / "pairs"
        inspect_pairs_cache_dir.mkdir(parents=True, exist_ok=True)
        verified_cache_dir = output_root / "cache" / "verified" / f"chainid_{chainid or 0}"
        verified_cache_dir.mkdir(parents=True, exist_ok=True)

        def rpc_call_hex(to: str, data: str) -> tuple[str | None, str | None]:
            try:
                return (rpc_eth_call(rpc_url, to, data), None)
            except Exception as exc:
                return (None, add_error_type("rpc", exc))

        def rpc_token0_token1(pair_addr: str) -> tuple[str | None, str | None, dict[str, Any]]:
            diag: dict[str, Any] = {}
            t0_hex, t0_err = rpc_call_hex(pair_addr, TOKEN0_SELECTOR)
            t1_hex, t1_err = rpc_call_hex(pair_addr, TOKEN1_SELECTOR)
            diag["token0()"] = {"ok": t0_err is None, "error": t0_err, "raw": t0_hex}
            diag["token1()"] = {"ok": t1_err is None, "error": t1_err, "raw": t1_hex}
            if not t0_hex or not t1_hex:
                return (None, None, diag)
            try:
                t0 = decode_eth_call_address(t0_hex)
                t1 = decode_eth_call_address(t1_hex)
            except Exception as exc:
                diag["decode"] = {"ok": False, "error": add_error_type("decode", exc)}
                return (None, None, diag)
            return (t0, t1, diag)

        def rpc_get_reserves_diag(pair_addr: str) -> tuple[tuple[int, int, int] | None, dict[str, Any]]:
            diag: dict[str, Any] = {}
            raw, err = rpc_call_hex(pair_addr, GETRESERVES_SELECTOR)
            diag["getReserves()"] = {"ok": err is None, "error": err, "raw": raw}
            if not raw:
                return (None, diag)
            try:
                s = raw.strip().lower()
                if not s.startswith("0x"):
                    raise ValueError(f"Unexpected getReserves result: {raw!r}")
                body = s[2:]
                if len(body) < 64 * 3:
                    raise ValueError(f"getReserves result too short: {raw!r}")
                r0 = int(body[0:64], 16)
                r1 = int(body[64:128], 16)
                ts = int(body[128:192], 16)
                return ((r0, r1, ts), diag)
            except Exception as exc:
                diag["decode"] = {"ok": False, "error": add_error_type("decode", exc)}
                return (None, diag)

        def rpc_balance_of_diag(token: str, owner: str) -> tuple[int | None, dict[str, Any]]:
            diag: dict[str, Any] = {}
            try:
                data = eth_call_data_with_address(BALANCEOF_SELECTOR, owner)
            except Exception as exc:
                diag["encode"] = {"ok": False, "error": add_error_type("encode", exc)}
                return (None, diag)
            raw, err = rpc_call_hex(token, data)
            diag["balanceOf()"] = {"ok": err is None, "error": err, "raw": raw}
            if not raw:
                return (None, diag)
            try:
                return (decode_eth_call_uint(raw), diag)
            except Exception as exc:
                diag["decode"] = {"ok": False, "error": add_error_type("decode", exc)}
                return (None, diag)

        def explorer_is_verified(address: str) -> bool | None:
            if not explorer_key:
                return None
            if cache_enabled:
                cache_path = verified_cache_dir / f"{address.lower()}.json"
                cached = _load_json_if_exists(cache_path)
                if isinstance(cached, dict) and "verdict" in cached:
                    v = cached.get("verdict")
                    if v is True or v is False:
                        return v
            try:
                data = get_sourcecode(api_base, explorer_key, address, chainid=chainid)
            except Exception as exc:
                add_error_type("explorer", exc)
                return None
            verdict = classify_verified_from_getsourcecode_response(data)
            if cache_enabled:
                # Cache only stable verdicts; "unknown" should be retried on later runs.
                if verdict is True or verdict is False:
                    _write_json_atomic(
                        verified_cache_dir / f"{address.lower()}.json",
                        {"address": address.lower(), "verdict": verdict, "ts": int(time.time())},
                    )
            return verdict

        results: list[dict[str, Any]] = []
        for i, raw in enumerate(addr_list, start=1):
            try:
                pair = normalize_address(raw)
            except ValueError:
                progress.update(i)
                continue
            progress.update(i, current=pair)

            # Per-pair cache (skip fully-complete entries).
            pair_cache_path = inspect_pairs_cache_dir / f"{pair}.json"
            if cache_enabled:
                cached_row = _load_json_if_exists(pair_cache_path)
                if isinstance(cached_row, dict) and str(cached_row.get("pair") or "").lower() == pair:
                    if _is_complete_inspect_row(cached_row):
                        results.append(cached_row)
                        continue
            attempts = max(0, int(args.pair_retries)) + 1
            last_row: dict[str, Any] | None = None
            for attempt in range(attempts):
                t0, t1, diag_tokens = rpc_token0_token1(pair)
                reserves, diag_reserves = rpc_get_reserves_diag(pair)
                r0, r1, ts = reserves if reserves else (None, None, None)
                b0, diag_b0 = rpc_balance_of_diag(t0, pair) if t0 else (None, {"skipped": True})
                b1, diag_b1 = rpc_balance_of_diag(t1, pair) if t1 else (None, {"skipped": True})

                if not explorer_key:
                    verified_pair = None
                    verified_token0 = None
                    verified_token1 = None
                else:
                    verified_pair = explorer_is_verified(pair)
                    verified_token0 = explorer_is_verified(t0) if t0 else None
                    verified_token1 = explorer_is_verified(t1) if t1 else None

                row = {
                    "pair": pair,
                    "token0": t0 or None,
                    "token1": t1 or None,
                    "reserve0": r0,
                    "reserve1": r1,
                    "blockTimestampLast": ts,
                    "balance0": b0,
                    "balance1": b1,
                    "verified": {
                        "pair": verified_pair,
                        "token0": verified_token0,
                        "token1": verified_token1,
                    },
                }
                last_row = row
                if _is_complete_inspect_row(row):
                    break
                if attempt + 1 < attempts:
                    # Brief backoff before retrying this pair end-to-end.
                    time.sleep(min(2.0, 0.2 * (2**attempt)))

            row = last_row or {"pair": pair}

            if row.get("token0") is None or row.get("token1") is None:
                add_null_reason("token0/token1 null: token detection failed (not a V2-style pair or RPC error)")
            if row.get("reserve0") is None or row.get("reserve1") is None or row.get("blockTimestampLast") is None:
                add_null_reason("reserve0/reserve1/blockTimestampLast null: getReserves() call failed or invalid output")
            if row.get("token0") is None:
                add_null_reason("balance0 null: token0 unknown (token detection failed)")
            elif row.get("balance0") is None:
                add_null_reason("balance0 null: balanceOf() call failed or invalid output")
            if row.get("token1") is None:
                add_null_reason("balance1 null: token1 unknown (token detection failed)")
            elif row.get("balance1") is None:
                add_null_reason("balance1 null: balanceOf() call failed or invalid output")

            verified = row.get("verified") if isinstance(row.get("verified"), dict) else {}
            if not explorer_key:
                add_null_reason("verified.* null: no explorer API key set (ETHERSCAN_API_KEY/BSCSCAN_API_KEY)")
            else:
                if verified.get("pair") is None:
                    add_null_reason("verified.pair null: explorer request failed/unknown (rate limit or error)")
                if row.get("token0") is None:
                    add_null_reason("verified.token0 null: token0 unknown (token detection failed)")
                elif verified.get("token0") is None:
                    add_null_reason("verified.token0 null: explorer request failed/unknown (rate limit or error)")
                if row.get("token1") is None:
                    add_null_reason("verified.token1 null: token1 unknown (token detection failed)")
                elif verified.get("token1") is None:
                    add_null_reason("verified.token1 null: explorer request failed/unknown (rate limit or error)")

            if cache_enabled and isinstance(row, dict) and _is_complete_inspect_row(row):
                _write_json_atomic(pair_cache_path, row)
            results.append(row)

        progress.done()
        null_reasons = [
            {"reason": reason, "count": count}
            for reason, count in sorted(null_reason_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        ]
        error_types = [
            {"type": label, "count": count}
            for label, count in sorted(error_type_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        ]
        payload = {
            "count": len(results),
            "results": results,
            "description": {"null_reasons": null_reasons, "error_types": error_types},
        }
        report_arg = str(args.report_json).strip()
        if report_arg == "-":
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            report_path = Path(report_arg) if report_arg else (output_root / "inspect_pairs_report.json")
            _write_json_atomic(report_path, payload)
            print(f"[ok] wrote {color_path(report_path)}")
        return 0

    if not addr_list:
        raise SystemExit("No input addresses. Provide pair addresses or use --factory.")

    if requires_chainid and chainid is None:
        raise SystemExit("--chainid is required when using the Etherscan API v2 base")
    api_key = ""
    try:
        api_key = load_api_key(Path(args.api_key_path) if args.api_key_path else None)
    except SystemExit:
        api_key = ""
    if bool(args.verified_only) and not api_key:
        raise SystemExit("--verified-only requires an explorer API key (set ETHERSCAN_API_KEY/BSCSCAN_API_KEY or pass --api-key-path)")

    progress = _Progress(
        "fetch",
        len(addr_list),
        enabled=not args.no_progress,
        every=args.progress_every,
    )
    for i, raw in enumerate(addr_list, start=1):
        try:
            pair_address = normalize_address(raw)
        except ValueError as exc:
            progress.log(f"[skip] {raw}: {exc}", stream=sys.stderr)
            progress.update(i)
            continue

        progress.update(i, current=pair_address)
        progress.log(f"[+] candidate: {pair_address}", stream=sys.stdout)
        pair_contract = load_verified_contract(api_base, api_key, pair_address, chainid=chainid)
        if bool(args.verified_only):
            if not pair_contract:
                progress.log(f"[skip] {pair_address}: not verified or fetch failed", stream=sys.stderr)
                continue
            time.sleep(sleep_s)
            group_dir = results_dir / pair_address
            contract_dir = group_dir / "contract"
            dump_contract(contract_dir, "contract", pair_contract)
            write_json(group_dir / "manifest.json", {"contract": pair_address})
            progress.log(f"[ok] wrote {color_path(group_dir)}", stream=sys.stdout)
            continue

        if not pair_contract:
            progress.log(f"[warn] {pair_address}: pair source not available on explorer; fetching tokens only", stream=sys.stderr)
        else:
            time.sleep(sleep_s)

        # Discover tokens via RPC if possible; otherwise you must pass pair addresses directly and accept skipping.
        if not rpc_url:
            progress.log(
                f"[skip] {pair_address}: --rpc-url is required to resolve token0/token1 for fetching",
                stream=sys.stderr,
            )
            continue

        tokens = rpc_detect_pair_tokens(rpc_url, pair_address)
        if not tokens:
            progress.log(f"[skip] {pair_address}: not a supported AMM pair (token0/token1)", stream=sys.stderr)
            continue
        token0, token1 = tokens
        progress.log(f"    token0: {token0}", stream=sys.stdout)
        progress.log(f"    token1: {token1}", stream=sys.stdout)

        token0_contract = load_verified_contract(api_base, api_key, token0, chainid=chainid)
        time.sleep(sleep_s)
        token1_contract = load_verified_contract(api_base, api_key, token1, chainid=chainid)
        time.sleep(sleep_s)

        if not token0_contract or not token1_contract:
            missing = []
            if not token0_contract:
                missing.append(f"token0 {token0}")
            if not token1_contract:
                missing.append(f"token1 {token1}")
            progress.log(f"[skip] {pair_address}: token not verified ({', '.join(missing)})", stream=sys.stderr)
            continue

        group_dir = results_dir / pair_address
        amm_dir = group_dir / "amm"
        tok0_dir = group_dir / "tokens" / token0
        tok1_dir = group_dir / "tokens" / token1

        if pair_contract:
            dump_contract(amm_dir, "amm", pair_contract)
        dump_contract(tok0_dir, "token0", token0_contract)
        dump_contract(tok1_dir, "token1", token1_contract)

        manifest = {
            "amm": pair_address,
            "token0": token0,
            "token1": token1,
        }
        write_json(group_dir / "manifest.json", manifest)
        progress.log(f"[ok] wrote {color_path(group_dir)}", stream=sys.stdout)

    progress.done()
    return 0


def _main_subcommand(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        description="AMM tools (subcommands). Legacy flag-based usage is still supported.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(subp: argparse.ArgumentParser) -> None:
        subp.add_argument("--rpc-url", default="", help="JSON-RPC URL.")
        subp.add_argument("--api-base", default=ETHERSCAN_V2_API_BASE, help="Explorer API base.")
        subp.add_argument("--chainid", type=int, default=0, help="Chain id for explorer v2.")
        subp.add_argument("--api-key-path", default="", help="Optional explorer API key file path.")
        subp.add_argument(
            "--verified-only",
            action="store_true",
            help="Fetch verified sources for provided addresses only (no AMM token0/token1 detection; --rpc-url not required).",
        )
        subp.add_argument("--sleep-ms", type=int, default=250, help="Sleep between explorer requests.")
        subp.add_argument("--output-dir", default="output", help="Local output/cache directory.")
        subp.add_argument("--no-cache", action="store_true", help="Disable local caching.")
        subp.add_argument("--progress-every", type=int, default=1, help="Print progress every N items.")
        subp.add_argument("--no-progress", action="store_true", help="Disable progress output.")
        subp.add_argument("--pair-retries", type=int, default=2, help="Retry incomplete pair inspections N times.")

    p_discover = sub.add_parser("discover", help="Discover pair addresses from a factory.")
    add_common(p_discover)
    p_discover.add_argument("--factory", required=True, help="Factory address to scan PairCreated logs.")
    p_discover.add_argument("--from-block", type=int, default=0, help="Start block.")
    p_discover.add_argument("--to-block", type=int, default=0, help="End block (0 means latest if --rpc-url is set).")
    p_discover.add_argument("--latest-blocks", type=int, default=0, help="Scan only latest N blocks.")
    p_discover.add_argument("--chunk-blocks", type=int, default=50_000, help="Block chunk size.")
    p_discover.add_argument("--token0", default="", help="Optional token0 filter.")
    p_discover.add_argument("--token1", default="", help="Optional token1 filter.")
    p_discover.add_argument("--topic0", default=PAIRCREATED_TOPIC0, help="Event signature topic0.")
    p_discover.add_argument("--pair-data-word", type=int, default=0, help="Data word index for pair address.")
    p_discover.add_argument("--max-pairs", type=int, default=0, help="Stop after discovering N pairs.")

    p_inspect = sub.add_parser("inspect", help="Inspect pairs (tokens/reserves/balances + optional verified).")
    add_common(p_inspect)
    p_inspect.add_argument("--pairs-file", default="", help="Pairs file (one address per line).")
    p_inspect.add_argument("addresses", nargs="*", help="Pair addresses.")
    p_inspect.add_argument("--report-json", default="", help="Report path (default: output/inspect_pairs_report.json; use '-' for stdout).")

    p_fetch = sub.add_parser("fetch", help="Fetch verified sources for pairs + their token contracts (alias: parse).")
    add_common(p_fetch)
    p_fetch.add_argument("--pairs-file", default="", help="Pairs file (one address per line).")
    p_fetch.add_argument("addresses", nargs="*", help="Pair addresses.")
    p_fetch.add_argument("--results-dir", default="", help="Where fetched sources are written (default: <output-dir>/fetch).")

    p_parse = sub.add_parser("parse", help="Parse/fetch verified sources into output/ (alias of fetch).")
    add_common(p_parse)
    p_parse.add_argument("--pairs-file", default="", help="Pairs file (one address per line).")
    p_parse.add_argument("addresses", nargs="*", help="Pair addresses.")
    p_parse.add_argument("--results-dir", default="", help="Where fetched sources are written (default: <output-dir>/fetch).")

    args = p.parse_args(argv)

    # Translate subcommands to legacy flags to keep behavior consistent.
    legacy: list[str] = []
    if args.cmd == "discover":
        legacy.extend(
            [
                "--factory",
                args.factory,
                "--discover-only",
                "--from-block",
                str(args.from_block),
                "--to-block",
                str(args.to_block),
                "--latest-blocks",
                str(args.latest_blocks),
                "--chunk-blocks",
                str(args.chunk_blocks),
                "--topic0",
                str(args.topic0),
                "--pair-data-word",
                str(args.pair_data_word),
                "--max-pairs",
                str(args.max_pairs),
            ]
        )
        if args.token0:
            legacy.extend(["--token0", str(args.token0)])
        if args.token1:
            legacy.extend(["--token1", str(args.token1)])
    elif args.cmd == "inspect":
        legacy.append("--inspect-pairs")
        if args.pairs_file:
            legacy.extend(["--pairs-file", str(args.pairs_file)])
        if args.report_json:
            legacy.extend(["--report-json", str(args.report_json)])
        legacy.extend(list(args.addresses or []))
    elif args.cmd in {"fetch", "parse"}:
        if args.pairs_file:
            legacy.extend(["--pairs-file", str(args.pairs_file)])
        legacy.extend(list(args.addresses or []))
        results_dir = str(args.results_dir).strip() or str(Path(args.output_dir) / "fetch")
        legacy.extend(["--results-dir", results_dir])

    # Shared flags.
    if args.rpc_url:
        legacy.extend(["--rpc-url", str(args.rpc_url)])
    legacy.extend(["--api-base", str(args.api_base)])
    if int(args.chainid) > 0:
        legacy.extend(["--chainid", str(int(args.chainid))])
    if args.api_key_path:
        legacy.extend(["--api-key-path", str(args.api_key_path)])
    if bool(args.verified_only):
        legacy.append("--verified-only")
    legacy.extend(["--sleep-ms", str(int(args.sleep_ms))])
    legacy.extend(["--output-dir", str(args.output_dir)])
    if bool(args.no_cache):
        legacy.append("--no-cache")
    legacy.extend(["--progress-every", str(int(args.progress_every))])
    if bool(args.no_progress):
        legacy.append("--no-progress")
    legacy.extend(["--pair-retries", str(int(args.pair_retries))])

    return main(legacy)
