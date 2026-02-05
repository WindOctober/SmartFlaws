# Gangster Finance (2025-06-20, BSC)

Root cause: `TokenVault.distribute()` “linearly drips” `dripPoolBalance` over time, but it does not cap `profit` to the pool balance and uses a non-reverting `safeSub` that returns 0 on underflow. When `lastPayout` is stale, `profit` can exceed `dripPoolBalance`, `dripPoolBalance` silently drops to 0, yet `profitPerShare_` is still increased by the full `profit`. This inflates dividends and allows `harvest()` to transfer real BTCB out of the vault.

Key addresses (BSC, from the write-up; not re-validated on-chain here):
- Victim (TokenVault): `0xe968d2e4adc89609773571301abec3399d163c3b`
- Underlying token (BTCB): `0x7130d2a12b9bcbfae4f2634d864a1ee1ce3ead9c`
- Attacker EOA: `0xc49f2938327aa2cdc3f2f89ed17b54b3671f05de`
- Exploit contract (unverified in our fetch): `0x982769c5e5dd77f8308e3cd6eec37da9d8237dc6`

Evidence (verified sources in this benchmark):
- `safeSub` underflows to 0 (no revert): `SmartFlaws/benchmark/Accounting/GangsterFinance_20250620/source/0xe968d2e4adc89609773571301abec3399d163c3b.sol#L49`
- `distribute()` computes `profit` from `dt` and updates `profitPerShare_` even when `profit > dripPoolBalance`: `SmartFlaws/benchmark/Accounting/GangsterFinance_20250620/source/0xe968d2e4adc89609773571301abec3399d163c3b.sol#L499`
- Balance is reduced with non-reverting `safeSub`: `SmartFlaws/benchmark/Accounting/GangsterFinance_20250620/source/0xe968d2e4adc89609773571301abec3399d163c3b.sol#L503`
- Dividends are paid out in `harvest()`: `SmartFlaws/benchmark/Accounting/GangsterFinance_20250620/source/0xe968d2e4adc89609773571301abec3399d163c3b.sol#L306`
- Transfer to the harvester: `SmartFlaws/benchmark/Accounting/GangsterFinance_20250620/source/0xe968d2e4adc89609773571301abec3399d163c3b.sol#L314`

Settings:
- `SmartFlaws/benchmark/Accounting/GangsterFinance_20250620/source/0xe968d2e4adc89609773571301abec3399d163c3b_settings.json`
