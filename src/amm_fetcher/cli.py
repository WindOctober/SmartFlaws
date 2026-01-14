from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from .constants import ETHERSCAN_V2_API_BASE, PAIRCREATED_TOPIC0
from .discovery import iter_pairs_from_factory_explorer, iter_pairs_from_factory_rpc
from .explorer import try_is_verified
from .inspect import rpc_detect_pair_tokens, rpc_erc20_balance_of, rpc_get_reserves
from .rpc import rpc_block_number
from .util import normalize_address, load_api_key, read_addresses_file, write_json, write_sources
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


def main(argv: list[str]) -> int:
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
        "--pairs-file",
        default="",
        help="Read pair addresses from a file (one per line, or output of --discover-only).",
    )
    p.add_argument(
        "--report-json",
        default="",
        help="Write inspection results to this JSON file (default: print JSON to stdout).",
    )
    p.add_argument(
        "--api-key-path",
        default="/home/work/.etherscan_api_key",
        help="Path to an Etherscan API key file (will also accept env ETHERSCAN_API_KEY).",
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
    if api_base == ETHERSCAN_V2_API_BASE and chainid is None:
        raise SystemExit("--chainid is required when using the Etherscan API v2 base")

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
        if not rpc_url:
            api_key = load_api_key(Path(args.api_key_path) if args.api_key_path else None)
            # best-effort: without RPC we can't resolve latest block; require explicit to_block
            if int(args.to_block) <= 0 and int(args.latest_blocks) <= 0:
                raise SystemExit("--to-block is required for explorer-based factory scans (or provide --rpc-url)")
        else:
            api_key = ""

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

        if rpc_url:
            pairs = iter_pairs_from_factory_rpc(
                args.factory,
                from_block,
                to_block,
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
            pairs = iter_pairs_from_factory_explorer(
                api_base,
                api_key,
                args.factory,
                from_block,
                to_block,
                chainid=chainid,
                topic0=args.topic0,
                chunk_blocks=args.chunk_blocks,
                sleep_s=sleep_s,
                token0_filter=args.token0 or None,
                token1_filter=args.token1 or None,
                pair_data_word=args.pair_data_word,
                max_pairs=args.max_pairs,
            )

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
        explorer_key = ""
        try:
            explorer_key = load_api_key(Path(args.api_key_path) if args.api_key_path else None)
        except SystemExit:
            explorer_key = ""

        results: list[dict[str, Any]] = []
        for raw in addr_list:
            try:
                pair = normalize_address(raw)
            except ValueError:
                continue
            tokens = rpc_detect_pair_tokens(rpc_url, pair)
            t0, t1 = tokens if tokens else ("", "")
            reserves = rpc_get_reserves(rpc_url, pair)
            r0, r1, ts = reserves if reserves else (None, None, None)
            b0 = rpc_erc20_balance_of(rpc_url, t0, pair) if t0 else None
            b1 = rpc_erc20_balance_of(rpc_url, t1, pair) if t1 else None

            results.append(
                {
                    "pair": pair,
                    "token0": t0 or None,
                    "token1": t1 or None,
                    "reserve0": r0,
                    "reserve1": r1,
                    "blockTimestampLast": ts,
                    "balance0": b0,
                    "balance1": b1,
                    "verified": {
                        "pair": try_is_verified(api_base, explorer_key, pair, chainid=chainid),
                        "token0": try_is_verified(api_base, explorer_key, t0, chainid=chainid) if t0 else None,
                        "token1": try_is_verified(api_base, explorer_key, t1, chainid=chainid) if t1 else None,
                    },
                }
            )

        payload = {"count": len(results), "results": results}
        if args.report_json:
            write_json(Path(args.report_json), payload)
            print(f"[ok] wrote {args.report_json}")
        else:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if not addr_list:
        raise SystemExit("No input addresses. Provide pair addresses or use --factory.")

    api_key = load_api_key(Path(args.api_key_path) if args.api_key_path else None)

    for raw in addr_list:
        try:
            pair_address = normalize_address(raw)
        except ValueError as exc:
            print(f"[skip] {raw}: {exc}", file=sys.stderr)
            continue

        print(f"[+] candidate: {pair_address}")
        pair_contract = load_verified_contract(api_base, api_key, pair_address, chainid=chainid)
        if not pair_contract:
            print(f"[skip] {pair_address}: not verified on explorer", file=sys.stderr)
            continue
        time.sleep(sleep_s)

        # Discover tokens via RPC if possible; otherwise you must pass pair addresses directly and accept skipping.
        if not rpc_url:
            print(f"[skip] {pair_address}: --rpc-url is required to resolve token0/token1 for fetching", file=sys.stderr)
            continue

        tokens = rpc_detect_pair_tokens(rpc_url, pair_address)
        if not tokens:
            print(f"[skip] {pair_address}: not a supported AMM pair (token0/token1)", file=sys.stderr)
            continue
        token0, token1 = tokens
        print(f"    token0: {token0}")
        print(f"    token1: {token1}")

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
            print(f"[skip] {pair_address}: token not verified ({', '.join(missing)})", file=sys.stderr)
            continue

        group_dir = results_dir / pair_address
        amm_dir = group_dir / "amm"
        tok0_dir = group_dir / "tokens" / token0
        tok1_dir = group_dir / "tokens" / token1

        dump_contract(amm_dir, "amm", pair_contract)
        dump_contract(tok0_dir, "token0", token0_contract)
        dump_contract(tok1_dir, "token1", token1_contract)

        manifest = {
            "amm": pair_address,
            "token0": token0,
            "token1": token1,
        }
        write_json(group_dir / "manifest.json", manifest)
        print(f"[ok] wrote {group_dir}")

    return 0

