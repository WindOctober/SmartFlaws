# BankrollNetworkStack (2025-06-19, BSC)

Root cause: the contract uses a “profitPerShare + payoutsTo” dividends model but mixes `uint256` math with `int256` accounting in `sell()`. A cast `(int256)(...)` can wrap, and Solidity `0.6.8` does not automatically revert on `int256` overflow/underflow. This can push `payoutsTo_[attacker]` into an invalid value, making `dividendsOf(attacker)` huge via `uint256(int256(...))` wraparound and enabling `withdraw()` to drain funds.

Key addresses / tx (BSC, from the write-up; not re-validated on-chain here):
- Victim: `0xAdEfb902CaB716B8043c5231ae9A50b8b4eE7c4e`
- Attacker EOA: `0x2deA406bb3bEa68d6be8D9Ef0071FDf63082Fb52`
- Exploit tx: `0x7226b3947c7e8651982e5bd777bca52d03ea31d19b515dec123595a4435ae22c`

Evidence (verified sources in this benchmark):
- `sell()` computes an `int256` from `uint256` math: `SmartFlaws/benchmark/Accounting/BankrollNetworkStack_20250619/source/0xadefb902cab716b8043c5231ae9a50b8b4ee7c4e.sol#L677`
- `sell()` updates `payoutsTo_` with unchecked `int256` subtraction: `SmartFlaws/benchmark/Accounting/BankrollNetworkStack_20250619/source/0xadefb902cab716b8043c5231ae9a50b8b4ee7c4e.sol#L678`
- Wraparound amplifier in `dividendsOf()`: `SmartFlaws/benchmark/Accounting/BankrollNetworkStack_20250619/source/0xadefb902cab716b8043c5231ae9a50b8b4ee7c4e.sol#L795`
- Drain path via `withdraw()`: `SmartFlaws/benchmark/Accounting/BankrollNetworkStack_20250619/source/0xadefb902cab716b8043c5231ae9a50b8b4ee7c4e.sol#L627`

Settings:
- `SmartFlaws/benchmark/Accounting/BankrollNetworkStack_20250619/source/0xadefb902cab716b8043c5231ae9a50b8b4ee7c4e_settings.json`
