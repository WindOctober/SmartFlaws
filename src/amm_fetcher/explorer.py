from __future__ import annotations

import json
import urllib.parse
from typing import Any

from .http import http_get_json
from .types import VerifiedContract
from .util import decode_sources, normalize_address


def scan_url(api_base: str, api_key: str, *, chainid: int | None = None, **params: str) -> str:
    qp = dict(params)
    qp["apikey"] = api_key
    if chainid is not None and chainid > 0:
        qp["chainid"] = str(chainid)
    return f"{api_base}?{urllib.parse.urlencode(qp)}"


def get_sourcecode(api_base: str, api_key: str, address: str, *, chainid: int | None = None) -> dict[str, Any]:
    url = scan_url(
        api_base,
        api_key,
        chainid=chainid,
        module="contract",
        action="getsourcecode",
        address=address,
    )
    data = http_get_json(url)
    if not isinstance(data, dict):
        raise RuntimeError(f"Unexpected getsourcecode response: {data!r}")
    return data


def load_verified_contract(api_base: str, api_key: str, address: str, *, chainid: int | None = None) -> VerifiedContract | None:
    data = get_sourcecode(api_base, api_key, address, chainid=chainid)
    result = data.get("result")
    if not isinstance(result, list) or not result:
        return None

    record = result[0]
    if not isinstance(record, dict):
        return None

    source_code = (record.get("SourceCode") or "").strip()
    abi_str = (record.get("ABI") or "").strip()
    if not source_code:
        return None
    if not abi_str or "not verified" in abi_str.lower():
        return None

    try:
        abi = json.loads(abi_str)
    except Exception:
        return None

    language = str(record.get("Language") or "Solidity")
    sources = decode_sources(source_code, language=language)
    if not sources:
        return None

    return VerifiedContract(
        address=address,
        contract_name=str(record.get("ContractName") or ""),
        compiler_version=str(record.get("CompilerVersion") or ""),
        language=language,
        abi=abi,
        sources=sources,
        raw_record=record,
    )


def classify_verified_from_getsourcecode_response(data: Any) -> bool | None:
    """
    Returns:
      - True: definitely verified (source + ABI present)
      - False: definitely not verified ("not verified" response)
      - None: unknown (API error, rate limit, unexpected shape)
    """
    if not isinstance(data, dict):
        return None

    status = str(data.get("status") or "").strip()
    message = str(data.get("message") or "").strip().lower()
    result = data.get("result")

    # Many explorers return status=0 for errors/rate limits; treat as unknown.
    if status == "0" or message == "notok":
        return None

    if not isinstance(result, list) or not result:
        return None

    record = result[0]
    if not isinstance(record, dict):
        return None

    source_code = str(record.get("SourceCode") or "").strip()
    abi_str = str(record.get("ABI") or "").strip()
    abi_lower = abi_str.lower()

    # Explicit "not verified" signals.
    if "not verified" in abi_lower or "contract source code not verified" in abi_lower:
        return False

    # Verified contracts should have both ABI and SourceCode.
    if not source_code:
        return None
    if not abi_str:
        return None

    return True


def try_is_verified(api_base: str, api_key: str, address: str, *, chainid: int | None = None) -> bool | None:
    if not api_key:
        return None
    try:
        data = get_sourcecode(api_base, api_key, normalize_address(address), chainid=chainid)
        return classify_verified_from_getsourcecode_response(data)
    except Exception:
        return None

