# LAUNDROMAT (2025-04-08, Ethereum)

Root cause: `deposit()` is payable but the `msg.value == payment` check is commented out, so anyone can register as a participant for free. Later, `withdrawFinal()` pays a fixed `payment` amount to `withdraw.sender` after signature flow completion, without any binding to “who actually paid”. An attacker can fill the participant slots with zero-ETH deposits and complete the withdrawal flow to drain ETH from the contract in `payment`-sized chunks.

Key info (Ethereum; tx not provided in metadata):
- Victim: `0x934cbbE5377358e6712b5f041D90313d935C501C`
- `arithAddress` (external ECC helper): `0x600ad7b57f3e6aeee53acb8704a5ed50b60cacd6` (from constants)

Evidence (verified sources in this benchmark):
- `deposit()` does not enforce `msg.value == payment`: `SmartFlaws/benchmark/LogicFlaw/LAUNDROMAT_20250408/source/0x934cbbe5377358e6712b5f041d90313d935c501c.sol#L83`
- Free registration still increments `gotParticipants`: `SmartFlaws/benchmark/LogicFlaw/LAUNDROMAT_20250408/source/0x934cbbe5377358e6712b5f041d90313d935c501c.sol#L82`
- Withdrawal flow stepper: `SmartFlaws/benchmark/LogicFlaw/LAUNDROMAT_20250408/source/0x934cbbe5377358e6712b5f041d90313d935c501c.sol#L112`
- Final payout always sends `payment` to `withdraw.sender`: `SmartFlaws/benchmark/LogicFlaw/LAUNDROMAT_20250408/source/0x934cbbe5377358e6712b5f041d90313d935c501c.sol#L176`

Settings:
- `SmartFlaws/benchmark/LogicFlaw/LAUNDROMAT_20250408/source/0x934cbbe5377358e6712b5f041d90313d935c501c_settings.json`
