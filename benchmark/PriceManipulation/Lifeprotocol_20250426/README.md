# Lifeprotocol (2025-04-26, BSC)

Root cause: the contract updates `currentPrice` upward in `handleRatio(...)` on `buy()`, but `sell()` prices payouts using `currentPrice` (with a fixed 10% discount) and does not call `handleRatio(...)` to adjust price downward. This asymmetric update lets an attacker pump `currentPrice` via repeated buys (often financed by flashloaned stablecoins), then immediately sell back at the inflated price to extract stablecoin reserves.

Key addresses / tx (BSC, from the write-up; not re-validated on-chain here):
- Exploit tx: `0x487fb71e3d2574e747c67a45971ec3966d275d0069d4f9da6d43901401f8f3c0`
- LifeProtocolContract: `0x42e2773508e2ae8ff9434bea599812e28449e2cd`
- Attacker EOA: `0x3026C464d3Bd6Ef0CeD0D49e80f171b58176Ce32`
- Attacker contract: `0xf6cee497dfe95a04faa26f3138f9244a4d92f942` (unverified / not fetched)
- Flashloan pool: `0x6098a5638d8d7e9ed2f952d35b2b67c34ec6b476`
- Quote token (USDT): `0x55d398326f99059ff775485246999027b3197955`

Evidence (verified sources in this benchmark):
- `buy()` updates price via `handleRatio(...)`: `SmartFlaws/benchmark/PriceManipulation/Lifeprotocol_20250426/source/0x42e2773508e2ae8ff9434bea599812e28449e2cd.sol#L1143`
- `sell()` uses `currentPrice` (90%): `SmartFlaws/benchmark/PriceManipulation/Lifeprotocol_20250426/source/0x42e2773508e2ae8ff9434bea599812e28449e2cd.sol#L1177`
- `sell()` ends without calling `handleRatio(...)` (it only calls `buyBack()`): `SmartFlaws/benchmark/PriceManipulation/Lifeprotocol_20250426/source/0x42e2773508e2ae8ff9434bea599812e28449e2cd.sol#L1223`
- `handleRatio(...)` definition (monotonic increase path): `SmartFlaws/benchmark/PriceManipulation/Lifeprotocol_20250426/source/0x42e2773508e2ae8ff9434bea599812e28449e2cd.sol#L1374`

Settings:
- `SmartFlaws/benchmark/PriceManipulation/Lifeprotocol_20250426/source/0x42e2773508e2ae8ff9434bea599812e28449e2cd_settings.json`
