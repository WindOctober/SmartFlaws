from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class VerifiedContract:
    address: str
    contract_name: str
    compiler_version: str
    language: str
    abi: Any
    sources: dict[str, str]
    raw_record: dict[str, Any]

