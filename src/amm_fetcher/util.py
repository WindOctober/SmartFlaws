from __future__ import annotations

import json
import os
from pathlib import Path, PurePosixPath
from typing import Any


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def load_api_key(api_key_path: Path | None) -> str:
    env_key = os.environ.get("BSCSCAN_API_KEY") or os.environ.get("ETHERSCAN_API_KEY")
    if env_key:
        return env_key.strip()
    if api_key_path is None:
        raise SystemExit("Missing API key: set BSCSCAN_API_KEY/ETHERSCAN_API_KEY or pass --api-key-path")
    if not api_key_path.exists():
        raise SystemExit(f"API key file not found: {api_key_path}")
    key = read_text(api_key_path)
    if not key:
        raise SystemExit(f"API key file is empty: {api_key_path}")
    return key


def is_hex_address(value: str) -> bool:
    v = value.strip()
    return len(v) == 42 and v.startswith("0x") and all(c in "0123456789abcdefABCDEF" for c in v[2:])


def normalize_address(addr: str) -> str:
    a = addr.strip()
    if not is_hex_address(a):
        raise ValueError(f"Invalid address: {addr}")
    return a.lower()


def safe_relpath(path_str: str) -> PurePosixPath:
    p = PurePosixPath(path_str.replace("\\", "/").lstrip("/"))
    if any(part == ".." for part in p.parts) or str(p) in ("", "."):
        raise ValueError(f"Unsafe source path: {path_str!r}")
    return p


def decode_eth_call_address(hex_result: str) -> str:
    s = (hex_result or "").strip()
    if not s.startswith("0x"):
        raise ValueError(f"Unexpected eth_call result: {hex_result!r}")
    if len(s) < 66:
        raise ValueError(f"eth_call result too short: {hex_result!r}")
    addr_hex = s[-40:]
    addr = "0x" + addr_hex
    if not is_hex_address(addr):
        raise ValueError(f"Invalid decoded address from eth_call: {hex_result!r}")
    return addr.lower()


def decode_eth_call_uint(hex_result: str) -> int:
    s = (hex_result or "").strip()
    if not s.startswith("0x"):
        raise ValueError(f"Unexpected eth_call result: {hex_result!r}")
    if len(s) < 66:
        raise ValueError(f"eth_call result too short: {hex_result!r}")
    return int(s, 16)


def encode_address_arg(addr: str) -> str:
    a = normalize_address(addr)
    return "0" * 24 + a[2:]


def eth_call_data_with_address(selector: str, addr: str) -> str:
    sel = selector.lower()
    if not sel.startswith("0x") or len(sel) != 10:
        raise ValueError(f"Bad selector: {selector!r}")
    return sel + encode_address_arg(addr)


def decode_sources(source_code_field: str, language: str) -> dict[str, str]:
    sc = (source_code_field or "").strip()
    if not sc:
        return {}

    if sc.startswith("{{") and sc.endswith("}}"):
        sc = sc[1:-1].strip()

    if sc.startswith("{") and ("\"sources\"" in sc or "'sources'" in sc):
        try:
            data = json.loads(sc)
            sources = data.get("sources")
            if isinstance(sources, dict) and sources:
                out: dict[str, str] = {}
                for filename, entry in sources.items():
                    if isinstance(entry, dict) and "content" in entry:
                        out[str(filename)] = str(entry.get("content") or "")
                    else:
                        out[str(filename)] = str(entry or "")
                return out
        except Exception:
            pass

    ext = "vy" if language.lower() == "vyper" else "sol"
    return {f"Contract.{ext}": sc}


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_sources(root: Path, sources: dict[str, str]) -> None:
    for rel_str, content in sources.items():
        rel = safe_relpath(rel_str)
        out_path = root / Path(*rel.parts)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")


def read_addresses_file(path: str) -> list[str]:
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"pairs file not found: {p}")
    out: list[str] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # allow lines like: "[+] discovered pair: 0xabc... (token0=..., token1=...)"
        for tok in line.replace("(", " ").replace(")", " ").replace(",", " ").split():
            if tok.startswith("0x") and len(tok) == 42:
                out.append(tok)
                break
    return out

