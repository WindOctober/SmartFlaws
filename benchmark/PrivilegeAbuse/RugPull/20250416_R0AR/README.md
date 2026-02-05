# R0AR / Roar (2025-04-16, Ethereum)

Root cause: an `Authorization` constructor writes a constant `NAME_HASH` into a constant storage slot `NAME_SLOT` via inline assembly. That fixed slot collides with the `R0ARStaking.userInfo[0][ATTACKER].amount` storage location, pre-setting the attacker’s `amount` to a huge value at deployment. The attacker then calls `EmergencyWithdraw(0)` to withdraw up to the pool’s entire LP token balance, because the function uses `user.amount` as the withdrawable amount (capped by the contract’s actual LP token balance).

Key addresses (Ethereum):
- Victim (R0ARStaking): `0xbd2cd71630f2da85399565f6f2b49c9d4ce0e77f`
- Pre-seeded attacker EOA: `0x8149f77504007450711023cf0ec11bdd6348401f`

Evidence (verified sources in this benchmark):
- Fixed slot and value constants: `SmartFlaws/benchmark/PrivilegeAbuse/RugPull/20250416_R0AR/0xbd2cd71630f2da85399565f6f2b49c9d4ce0e77f.sol#L668`
- Backdoor write in constructor (`sstore(NAME_SLOT, NAME_HASH)`): `SmartFlaws/benchmark/PrivilegeAbuse/RugPull/20250416_R0AR/0xbd2cd71630f2da85399565f6f2b49c9d4ce0e77f.sol#L675`
- `userInfo` mapping definition (collision target): `SmartFlaws/benchmark/PrivilegeAbuse/RugPull/20250416_R0AR/0xbd2cd71630f2da85399565f6f2b49c9d4ce0e77f.sol#L994`
- `EmergencyWithdraw()` uses `user.amount` as withdrawable amount: `SmartFlaws/benchmark/PrivilegeAbuse/RugPull/20250416_R0AR/0xbd2cd71630f2da85399565f6f2b49c9d4ce0e77f.sol#L1129`
- Transfer is capped only by the contract’s LP token balance: `SmartFlaws/benchmark/PrivilegeAbuse/RugPull/20250416_R0AR/0xbd2cd71630f2da85399565f6f2b49c9d4ce0e77f.sol#L1143`

Settings:
- `SmartFlaws/benchmark/PrivilegeAbuse/RugPull/20250416_R0AR/0xbd2cd71630f2da85399565f6f2b49c9d4ce0e77f_settings.json`
