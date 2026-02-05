# ResupplyFi (2025-06-26, Ethereum)

Root cause: the protocol’s solvency check relies on a per-tx snapshot exchange rate computed from an oracle price of the collateral token (here the collateral vault token `cvcrvUSD`). If the collateral’s spot price can be manipulated atomically (e.g., via ERC4626 share price “donations” that change `totalAssets` without minting shares), an attacker can temporarily overvalue collateral, borrow, and mint excess `reUSD`, then unwind the manipulation.

Key addresses (Ethereum):
- Victim market (ResupplyPair): `0x6e90c85a495d54c6d7E1f3400FEF1f6e59f86bd6`
- Registry (mints debt token): `0x10101010e0c3171d894b71b3400668af311e7d94`
- Debt token (reUSD): `0x57ab1e0003f623289cd798b1824be09a793e4bec`
- Collateral vault token (`cvcrvUSD`): `0x01144442fba7adccb5c9dc9cf33dd009d50a9e1d`
- `cvcrvUSD.controller()` (Curve Controller): `0x89707721927d7aaeeee513797A8d6cBbD0e08f41`
- Exploit tx: `0xffbbd492e0605a8bb6d490c3cd879e87ff60862b0684160d08fd5711e7a872d3`
- Attacker EOA: `0x6D9f6E900ac2CE6770Fd9f04f98B7B0fc355E2EA`

Notes on source availability:
- This benchmark includes ResupplyFi protocol sources under `SmartFlaws/benchmark/Oracle/ResupplyFi_20250626/source/src/...`.
- `cvcrvUSD` (`0x0114…`) source is not present in this snapshot, so the share-price manipulation detail is described conceptually.
- The controller contract source is included and exposes `total_debt()`: `SmartFlaws/benchmark/Oracle/ResupplyFi_20250626/source/0x89707721927d7aaeeee513797a8d6cbbd0e08f41.sol#L454`.

Evidence (protocol path in this benchmark):
- `borrow()` is guarded by `isSolvent(msg.sender)` (post-check) but uses the stored exchange rate: `SmartFlaws/benchmark/Oracle/ResupplyFi_20250626/source/src/protocol/pair/ResupplyPairCore.sol#L677`
- `isSolvent` reads `exchangeRateInfo.exchangeRate`: `SmartFlaws/benchmark/Oracle/ResupplyFi_20250626/source/src/protocol/pair/ResupplyPairCore.sol#L298`
- `_updateExchangeRate()` writes `exchangeRateInfo.exchangeRate` from the collateral oracle price: `SmartFlaws/benchmark/Oracle/ResupplyFi_20250626/source/src/protocol/pair/ResupplyPairCore.sol#L564`
- Debt minting: `ResupplyRegistry.mint()` → `Stablecoin.mint()`: `SmartFlaws/benchmark/Oracle/ResupplyFi_20250626/source/src/protocol/ResupplyRegistry.sol#L229`, `SmartFlaws/benchmark/Oracle/ResupplyFi_20250626/source/Stablecoin.sol#L38`
