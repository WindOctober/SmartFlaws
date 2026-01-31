#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _bootstrap_src() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo_root / "src"))


_bootstrap_src()

from amm_fetcher.explorer import load_verified_contract  # noqa: E402
from amm_fetcher.rpc import rpc_call  # noqa: E402
from amm_fetcher.util import load_api_key, normalize_address, write_json, write_sources  # noqa: E402


def _safe_rpc_call(rpc_url: str, method: str, params: list[Any]) -> dict[str, Any]:
    try:
        return {"ok": True, "result": rpc_call(rpc_url, method, params)}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _dump_verified_contract(out_dir: Path, kind: str, vc: Any) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "kind": kind,
        "address": getattr(vc, "address", ""),
        "contractName": getattr(vc, "contract_name", ""),
        "language": getattr(vc, "language", ""),
        "compilerVersion": getattr(vc, "compiler_version", ""),
    }
    write_json(out_dir / "metadata.json", meta)
    write_json(out_dir / "abi.json", getattr(vc, "abi", None))
    write_json(out_dir / "explorer_record.json", getattr(vc, "raw_record", None))
    sources = getattr(vc, "sources", None)
    if isinstance(sources, dict):
        write_sources(out_dir / "source", sources)


def _load_report(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"Bad report JSON shape: {path}")
    return data


def _select_pairs(results: list[dict[str, Any]], *, pairs: set[str] | None, only_token_null: bool) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for entry in results:
        if not isinstance(entry, dict):
            continue
        pair = str(entry.get("pair") or "").strip()
        if not pair:
            continue
        try:
            pair = normalize_address(pair)
        except Exception:
            continue

        if pairs is not None and pair not in pairs:
            continue
        if only_token_null and not (entry.get("token0") is None or entry.get("token1") is None):
            continue
        out.append({**entry, "pair": pair})
    return out


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Debug/dump info for pairs in an --inspect-pairs JSON report.")
    p.add_argument("--report-json", required=True, help="Path to the JSON report produced by --inspect-pairs.")
    p.add_argument("--rpc-url", required=True, help="JSON-RPC URL for eth_getCode/eth_call inspection.")
    p.add_argument("--output-dir", default="output", help="Directory to write debug artifacts (default: output/).")
    p.add_argument("--pair", action="append", default=[], help="Only debug this pair address (repeatable).")
    p.add_argument("--max", type=int, default=0, help="Limit number of pairs processed (0 means no limit).")
    p.add_argument(
        "--only-token-null",
        action="store_true",
        help="Only include entries where token0 or token1 is null.",
    )
    p.add_argument(
        "--fetch-source",
        action="store_true",
        help="If set, also download verified source/ABI via explorer (requires ETHERSCAN_API_KEY/BSCSCAN_API_KEY and --chainid).",
    )
    p.add_argument(
        "--api-base",
        default="https://api.etherscan.io/v2/api",
        help="Explorer API base (default: https://api.etherscan.io/v2/api).",
    )
    p.add_argument("--chainid", type=int, default=0, help="Chain id for explorer v2 (required for --fetch-source).")
    args = p.parse_args(argv)

    report_path = Path(args.report_json)
    out_root = Path(args.output_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    report = _load_report(report_path)
    results = report.get("results")
    if not isinstance(results, list):
        raise SystemExit(f"Missing/invalid results[] in report: {report_path}")

    pair_filter: set[str] | None = None
    if args.pair:
        pair_filter = set()
        for raw in args.pair:
            pair_filter.add(normalize_address(raw))

    selected = _select_pairs(results, pairs=pair_filter, only_token_null=bool(args.only_token_null))
    if args.max and args.max > 0:
        selected = selected[: int(args.max)]

    api_key = ""
    if args.fetch_source:
        if int(args.chainid) <= 0:
            raise SystemExit("--fetch-source requires --chainid")
        api_key = load_api_key(None)

    for entry in selected:
        pair = str(entry["pair"])
        pair_dir = out_root / pair
        pair_dir.mkdir(parents=True, exist_ok=True)

        diag: dict[str, Any] = {
            "pair": pair,
            "from_report": entry,
            "rpc": {
                "eth_getCode": _safe_rpc_call(args.rpc_url, "eth_getCode", [pair, "latest"]),
                "eth_call": {
                    # token0(), token1(), getReserves()
                    "token0()": _safe_rpc_call(args.rpc_url, "eth_call", [{"to": pair, "data": "0x0dfe1681"}, "latest"]),
                    "token1()": _safe_rpc_call(args.rpc_url, "eth_call", [{"to": pair, "data": "0xd21220a7"}, "latest"]),
                    "getReserves()": _safe_rpc_call(args.rpc_url, "eth_call", [{"to": pair, "data": "0x0902f1ac"}, "latest"]),
                },
            },
        }

        write_json(pair_dir / "diagnostics.json", diag)

        code = diag["rpc"]["eth_getCode"]
        if isinstance(code, dict) and code.get("ok") and isinstance(code.get("result"), str):
            code_hex: str = code["result"]
            (pair_dir / "bytecode.hex").write_text(code_hex + "\n", encoding="utf-8")

        if args.fetch_source:
            try:
                vc = load_verified_contract(args.api_base, api_key, pair, chainid=int(args.chainid))
            except Exception as exc:
                (pair_dir / "explorer_missing.txt").unlink(missing_ok=True)
                (pair_dir / "explorer_error.txt").write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
            else:
                (pair_dir / "explorer_error.txt").unlink(missing_ok=True)
                if vc is None:
                    (pair_dir / "explorer_missing.txt").write_text(
                        "not verified (or explorer returned empty)\n",
                        encoding="utf-8",
                    )
                else:
                    (pair_dir / "explorer_missing.txt").unlink(missing_ok=True)
                    _dump_verified_contract(pair_dir / "explorer" / "pair", "pair", vc)

    index = {
        "report": str(report_path),
        "output_dir": str(out_root),
        "count": len(selected),
        "pairs": [e["pair"] for e in selected],
    }
    write_json(out_root / "index.json", index)
    print(f"[ok] wrote {out_root / 'index.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
