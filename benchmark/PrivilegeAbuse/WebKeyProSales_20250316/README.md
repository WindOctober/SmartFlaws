# WebKeyProSales (2025-03-16, BSC)

Root cause: `WebKeyProSales` sells a fixed “package” at `currentSaleInfo.price` and immediately mints/releases `immediateReleaseTokens` to the buyer, but there is no constraint tying `price` (or release amount) to any market price (AMM) or oracle. If the privileged operator misconfigures `currentSaleInfo` (or the operator key is compromised), the contract becomes a deterministic arbitrage target: flashloan → `buy()` → dump on AMM → repay, repeat.

Key addresses / tx (BSC, from the write-up; not re-validated on-chain here):
- Sales proxy: `0xD511096a73292A7419a94354d4C1C73e8a3CD851`
- Sales implementation: `0xc39c54868a4f842b02a99339f4a57a44efc310b8`
- wKeyDAO token: `0x194B302a4b0a79795Fb68E2ADf1B8c9eC5ff8d1F`
- Attack contract (verified in this benchmark): `0x3783c91ee49a303c17c558f92bf8d6395d2f76e3`
- Exploit tx: `0xc9bccafdb0cd977556d1f88ac39bf8b455c0275ac1dd4b51d75950fb58bad4c8`

- Mispricing config entrypoint: `SmartFlaws/benchmark/PrivilegeAbuse/WebKeyProSales_20250316/source/contracts/webkey/Sales.sol#L95`
- Fixed-price buy + immediate mint/release: `SmartFlaws/benchmark/PrivilegeAbuse/WebKeyProSales_20250316/source/contracts/webkey/Sales.sol#L121`
- Token mint gated by role (`MINT`): `SmartFlaws/benchmark/PrivilegeAbuse/WebKeyProSales_20250316/source/ERC20.sol#L418`
- Attacker loop (buy → swap dump): `SmartFlaws/benchmark/PrivilegeAbuse/WebKeyProSales_20250316/source/0x3783c91ee49a303c17c558f92bf8d6395d2f76e3.sol#L441`
