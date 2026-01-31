# MulticallWithXera

Root cause: the victim address granted ERC20 allowance to the public `Multicall3` forwarder; since `aggregate3` is permissionless, any attacker can route an `ERC20.transferFrom(victim, to, amount)` through `Multicall3` (as the spender) and drain the victim's tokens.

Attack path:
- Victim has XERA balance and an allowance `allowance[victim][Multicall3] > 0`.
- Attacker calls `Multicall3.aggregate3([{target: XERA, callData: transferFrom(victim, attackerControlled, amount)}])`.
- XERA checks allowance against `spender = msg.sender` (i.e. `Multicall3`), so the transfer succeeds.
- Attacker swaps the stolen XERA via the Pancake pair to cash out.

Evidence:
- Permissionless forwarder: `SmartFlaws/benchmark/AccessControl/MulticallWithXera/source/contracts/Multicall3.sol:98`
- Allowance enforced on `spender=_msgSender()`: `SmartFlaws/benchmark/AccessControl/MulticallWithXera/source/contracts/ERC20.sol:154`
- Victim minted initial supply (balance source): `SmartFlaws/benchmark/AccessControl/MulticallWithXera/source/contracts/Token.sol:101`

Contracts (BSC):
- Multicall3: `0xcA11bde05977b3631167028862bE2a173976CA11`
- XERA (LUXERA): `0x93E99aE6692b07A36E7693f4ae684c266633b67d`
- Pancake pair: `0x231075E4AA60d28681a2d6D4989F8F739BAC15a0`
- Victim (supply recipient): `0x9a619Ae8995A220E8f3A1Df7478A5c8d2afFc542`

Reproduction reference (DeFiHackLabs):
- PoC: `DeFiHackLabs/src/test/2025-08/MulticallWithXera_exp.sol`
- Attack tx: `0xed6fd61c1eb2858a1594616ddebaa414ad3b732dcdb26ac7833b46803c5c18db`

Settings (explorer getsourcecode records):
- `SmartFlaws/benchmark/AccessControl/MulticallWithXera/source/0xca11bde05977b3631167028862be2a173976ca11_settings.json`
- `SmartFlaws/benchmark/AccessControl/MulticallWithXera/source/0x93e99ae6692b07a36e7693f4ae684c266633b67d_settings.json`
- `SmartFlaws/benchmark/AccessControl/MulticallWithXera/source/0x231075e4aa60d28681a2d6d4989f8f739bac15a0_settings.json`

