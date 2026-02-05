# BTNFT (2025-04-18, BSC)

Root cause: BTNFT overrides OpenZeppelin ERC721 `_update(...)` and turns `to == address(this)` into a reward-claim trigger that **skips authorization** and **skips the actual NFT transfer**, then pays rewards to `msg.sender`. An attacker can call `transferFrom(realOwner, address(BTNFT), tokenId)` without approval and drain vested rewards across many `tokenId`s.

Key addresses / tx (BSC):
- BTNFT (victim): `0x0fc91b6fea2e7a827a8c99c91101ed36c638521b`
- Attacker EOA: `0x7a4d144307d2dfa2885887368e4cd4678db3c27a`
- Exploit tx: `0x1e90cbff665c43f91d66a56b4aa9ba647486a5311bb0b4381de4d653a9d8237d`
- Reward token (BTT): `0xDAd4df3eFdb945358a3eF77B939Ba83DAe401DA8`

Evidence (verified sources in this benchmark):
- Base auth check that should run: `SmartFlaws/benchmark/AccessControl/BTNFT_20250418/source/0x0fc91b6fea2e7a827a8c99c91101ed36c638521b.sol#L3421`
- BTNFT `_update(...)` early-return branch: `SmartFlaws/benchmark/AccessControl/BTNFT_20250418/source/0x0fc91b6fea2e7a827a8c99c91101ed36c638521b.sol#L3915`
- Reward paid to caller (`msg.sender`): `SmartFlaws/benchmark/AccessControl/BTNFT_20250418/source/0x0fc91b6fea2e7a827a8c99c91101ed36c638521b.sol#L3928`

Settings (explorer getsourcecode record):
- `SmartFlaws/benchmark/AccessControl/BTNFT_20250418/source/0x0fc91b6fea2e7a827a8c99c91101ed36c638521b_settings.json`
