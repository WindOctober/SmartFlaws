# MetaPool (2025-06-17, Ethereum)

Root cause: MetaPool’s `Staking` vault customizes ERC4626 deposit logic for ETH/WETH but leaves the standard ERC4626 `mint(shares, receiver)` entrypoint enabled. OZ’s `mint()` computes `assets = previewMint(shares)` and calls `_deposit(...)`, but `Staking._deposit(...)` does **not** transfer WETH and does **not** check `msg.value == assets`. As a result, a caller can invoke `mint()` to receive shares while providing no assets.

Key addresses / tx (Ethereum, from the write-up; not re-validated on-chain here):
- mpETH proxy: `0x48AFbBd342F64EF8a9Ab1C143719b63C2AD81710`
- Staking implementation (source fetched for this benchmark): `0x3747484567119592ff6841df399cf679955a111a`
- Example exploit tx: `0x57ee419a001d85085478d04dd2a73daa91175b1d7c11d8a8fb5622c56fd1fa69`

Evidence (verified sources in this benchmark):
- OZ `ERC4626Upgradeable.mint()` calls `_deposit(...)` after `previewMint(...)`: `SmartFlaws/benchmark/Accounting/MetaPool_20250617/source/@openzeppelin/contracts-upgradeable/token/ERC20/extensions/ERC4626Upgradeable.sol#L143`
- `deposit(...)` is the only path that actually does `safeTransferFrom(...)`: `SmartFlaws/benchmark/Accounting/MetaPool_20250617/source/contracts/Staking.sol#L337`
- `_deposit(...)` mints shares and accounts `totalUnderlying` but does not pull assets: `SmartFlaws/benchmark/Accounting/MetaPool_20250617/source/contracts/Staking.sol#L355`

Settings:
- `SmartFlaws/benchmark/Accounting/MetaPool_20250617/source/0x3747484567119592ff6841df399cf679955a111a_settings.json`
- `SmartFlaws/benchmark/Accounting/MetaPool_20250617/source/0x48afbbd342f64ef8a9ab1c143719b63c2ad81710_settings.json`
