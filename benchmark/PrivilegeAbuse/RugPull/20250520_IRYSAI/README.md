# IRYSAI (2025-05-20, BSC)

Root cause: on sells (`to == uniswapV2Pair`) the token swaps accumulated fee tokens for BNB/ETH and then transfers the entire contract ETH balance to `_taxWallet`. `_taxWallet` can be changed by any caller who is `_excludedFromFee[msg.sender]` (initially the deployer/initial tax wallet). This enables a privileged actor to redirect fee proceeds to an arbitrary EOA/contract and drain value from trading activity.

Key addresses / tx (BSC, from the write-up; not re-validated on-chain here):
- Token (IRYSAI): `0x746727FC8212ED49510a2cB81ab0486Ee6954444`
- PancakeSwap V2 pair (IRYSAI/WBNB): `0xeB703Ed8C1A3B1d7E8E29351A1fE5E625E2eFe04`
- Tax wallet set to a contract: `0x6233a81BbEcb355059DA9983D9fC9dFB86D7119f` (source not fetched)
- Tx (set tax wallet): `0x8c637fc98ad84b922e6301c0b697167963eee53bbdc19665f5d122ae55234ca6`
- Tx (rug / drain): `0xe9a66bad8975f2a7b68c74992054c84d6d80ac4c543352e23bf23740b8858645`

Evidence (verified sources in this benchmark):
- Sell hook triggers swap + fee forwarding: `SmartFlaws/benchmark/PrivilegeAbuse/RugPull/20250520_IRYSAI/contracts/CA.sol#L322`
- Fee forwarding to `_taxWallet`: `SmartFlaws/benchmark/PrivilegeAbuse/RugPull/20250520_IRYSAI/contracts/CA.sol#L362`
- `setTaxWallet()` gated only by `_excludedFromFee[msg.sender]`: `SmartFlaws/benchmark/PrivilegeAbuse/RugPull/20250520_IRYSAI/contracts/CA.sol#L429`

Settings:
- `SmartFlaws/benchmark/PrivilegeAbuse/RugPull/20250520_IRYSAI/0x746727fc8212ed49510a2cb81ab0486ee6954444_settings.json`
- `SmartFlaws/benchmark/PrivilegeAbuse/RugPull/20250520_IRYSAI/0xeb703ed8c1a3b1d7e8e29351a1fe5e625e2efe04_settings.json`
