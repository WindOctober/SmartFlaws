#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap_src() -> None:
    src_dir = Path(__file__).resolve().parent.parent / "src"
    sys.path.insert(0, str(src_dir))


_bootstrap_src()

from amm_fetcher.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
