# AaveBoost (2025-06-12, Ethereum)

Root cause: `proxyDeposit(asset, recipient, amount)` has a “reward deposit” branch that always deposits `amount + REWARD` into the external pool, but only transfers `amount` from the caller. When `amount == 0`, the caller pays nothing while the pool pulls `REWARD` from AaveBoost’s own AAVE balance (AaveBoost grants the pool an infinite allowance in the constructor). This lets an attacker repeatedly drain the pre-funded reward balance.

Key addresses (Ethereum, from the write-up; not re-validated on-chain here):
- AaveBoost: `0xd2933c86216dC0c938FfAFEca3C8a2D6e633e2cA`
- AAVE token: `0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9`
- Pool (non-core legacy component): `0xF36F3976f288B2B4903aCA8C177EFC019b81D88b`
- Attacker EOA: `0x5D4430D14aE1d11526ddAc1c1eF01DA3b1DaE455`
- Example attack tx: `0xc4ef3b5e39d862ffcb8ff591fbb587f89d9d4ab56aec70cfb15831782239c0ce`

Evidence (verified sources in this benchmark):
- Infinite allowance to the pool: `SmartFlaws/benchmark/LogicFlaw/AaveBoost_20250612/source/contracts/AaveBoost.sol#L27`
- Reward branch does `transferFrom(..., amount)` then deposits `amount + REWARD`: `SmartFlaws/benchmark/LogicFlaw/AaveBoost_20250612/source/contracts/AaveBoost.sol#L48`
- Missing validation tying `asset` to `aave` (reward accounting uses `aave.balanceOf(this)`, but deposits arbitrary `asset`): `SmartFlaws/benchmark/LogicFlaw/AaveBoost_20250612/source/contracts/AaveBoost.sol#L43`

Settings:
- `SmartFlaws/benchmark/LogicFlaw/AaveBoost_20250612/source/0xd2933c86216dc0c938ffafeca3c8a2d6e633e2ca_settings.json`
