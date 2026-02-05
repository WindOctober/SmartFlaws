# SilicaPools (2025-03-28, Ethereum)

Root cause: `SilicaPools` tracks `PoolState.sharesMinted` as a `uint128`, but mints ERC1155 long/short shares in `uint256`. During mint, the contract performs an unsafe narrowing cast `uint128(shares)` which truncates when `shares > 2^128-1`, desyncing (a) the recorded total shares (`sharesMinted`) from (b) the actual ERC1155 supply/balances. Redemption then uses the attacker’s full `uint256` `shortSharesBalance` divided by the truncated `sharesMinted`, producing over-redemption in `redeemShort()`.

Key addresses / tx (Ethereum, from the write-up; not re-validated on-chain here):
- Victim: `0xf3f84ce038442ae4c4dcb6a8ca8bacd7f28c9bde`
- Attacker EOA: `0xF6ffBa5cbF285824000daC0B9431032169672B6e`
- Attacker contract (source not fetched in this repo): `0x80bf7db69556d9521c03461978b8fc731dbbd4e4`
- Exploit tx: `0x9b9a6dd05526a8a4b40e5e1a74a25df6ecccae6ee7bf045911ad89a1dd3f0814`

- Truncating state update: `SmartFlaws/benchmark/PrecisionLoss/SilicaPools_20250328/source/contracts/SilicaPools.sol#L837`
- ERC1155 mint uses full `shares`: `SmartFlaws/benchmark/PrecisionLoss/SilicaPools_20250328/source/contracts/SilicaPools.sol#L839`
- `redeemShort()` payout path: `SmartFlaws/benchmark/PrecisionLoss/SilicaPools_20250328/source/contracts/SilicaPools.sol#L686`
- Payout divides by `sState.sharesMinted`: `SmartFlaws/benchmark/PrecisionLoss/SilicaPools_20250328/source/libraries/PoolMaths.sol#L42`
- `sharesMinted` type (`uint128`) definition: `SmartFlaws/benchmark/PrecisionLoss/SilicaPools_20250328/source/interfaces/ISilicaPools.sol#L165`
