# Bebop JAM Settlement (Arbitrary User Input)

Root cause: `JamSettlement.settle(...)` executes a user-supplied list of arbitrary external calls ("interactions").
If a user mistakenly approves the *settlement* contract as an ERC20 spender (instead of approving the per-settlement `balanceManager`), any external caller can route `ERC20.transferFrom(victim, attacker, amount)` through those interactions and drain the victim's tokens (spender=`JamSettlement`).

Why this is commonly labeled "Arbitrary user input":
- The attacker controls `(to, value, data)` for each interaction and the contract performs a raw `.call(...)` with those bytes.
- The only guard is that `to != balanceManager`, which does not prevent calling arbitrary token contracts.

Evidence (verified sources, Base):
- User-controlled arbitrary call: `SmartFlaws/benchmark/AccessControl/BebopJAMSettlement/source/src/libraries/JamInteraction.sol:21`
- Settlement executes user-provided interactions during settlement: `SmartFlaws/benchmark/AccessControl/BebopJAMSettlement/source/src/JamSettlement.sol:47`
- BalanceManager is a separate contract deployed by `JamSettlement` (the *intended* approval target): `SmartFlaws/benchmark/AccessControl/BebopJAMSettlement/source/src/base/JamValidation.sol:33`

Contracts (Base):
- JAM Settlement: `0xbeb0b0623f66bE8cE162EbDfA2ec543A522F4ea6`
- Balance Manager (read via `balanceManager()`): `0xC5a350853E4E36b73eB0C24aAA4B8816c9A3579a`

Reproduction reference (DeFiHackLabs):
- PoC: `DeFiHackLabs/src/test/2025-08/Bebop_dex_exp.sol`
- Notes: the PoC forks Arbitrum, but the exploit pattern is chain-agnostic when the same settlement design is deployed and users mistakenly approve the settlement contract.

Settings (explorer getsourcecode record):
- `SmartFlaws/benchmark/AccessControl/BebopJAMSettlement/source/0xbeb0b0623f66be8ce162ebdfa2ec543a522f4ea6_settings.json`
- `SmartFlaws/benchmark/AccessControl/BebopJAMSettlement/source/0xc5a350853e4e36b73eb0c24aaa4b8816c9a3579a_settings.json`
