# SmartFlaws

This repository curates collected smart-contract vulnerabilities and provides the related contract benchmarks necessary to analyze those flaws. The dataset is intended for research, experimentation, and evaluation in smart-contract static analysis and vulnerability detection.

## Tools

### `fetch_bsc_amm.py`

Fetch and inspect UniswapV2/PancakeV2-style AMM pairs.

- Discovery (find pairs) uses `PairCreated` logs from a factory (RPC preferred).
- Inspection (per pair) uses RPC to read `token0/token1`, `getReserves`, and `balanceOf(pair)` for both tokens.
- Verified-source checks use **Etherscan API v2** `getsourcecode` (requires `--chainid`).

#### Requirements

- Python 3.10+
- A JSON-RPC endpoint for the target chain (`--rpc-url`)
- An Etherscan API key for verified checks / source download (read from `--api-key-path` or env `ETHERSCAN_API_KEY`)

#### Common Parameters

- `--rpc-url`: JSON-RPC endpoint (used for discovery via `eth_getLogs` and for on-chain inspection).
- `--api-base`: Explorer API base (default `https://api.etherscan.io/v2/api`).
- `--chainid`: Required when using Etherscan API v2 (e.g. `56` BSC, `137` Polygon, `42161` Arbitrum, `10` Optimism, `8453` Base, `43114` Avalanche C-Chain, `250` Fantom).
- `--api-key-path`: Path to a file containing an API key (default `/home/work/.etherscan_api_key`).
- `--results-dir`: Where fetched sources are written (default `results/`).

#### Examples

Discover pairs from a factory (BSC PancakeSwap V2), print only:

```bash
python3 SmartFlaws/fetch_bsc_amm.py \
  --factory 0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73 \
  --latest-blocks 5000 \
  --discover-only \
  --rpc-url https://1rpc.io/bnb
```

Inspect pairs (from a discovery output file), and write a JSON report:

```bash
python3 SmartFlaws/fetch_bsc_amm.py \
  --inspect-pairs \
  --pairs-file /tmp/pancake_pairs_latest5000.txt \
  --rpc-url https://1rpc.io/bnb \
  --api-key-path /home/work/.etherscan_api_key \
  --chainid 56 \
  --report-json /tmp/pancake_pairs_report.json
```

Fetch verified sources for a specific pair + its token contracts (requires both RPC and explorer key):

```bash
python3 SmartFlaws/fetch_bsc_amm.py \
  0x54d16bb1e9e5ea657ab81fbdeae51d762e5e5b50 \
  --rpc-url https://1rpc.io/bnb \
  --api-key-path /home/work/.etherscan_api_key \
  --chainid 56 \
  --results-dir results
```
