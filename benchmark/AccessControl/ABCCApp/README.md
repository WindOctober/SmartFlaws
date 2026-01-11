# ABCCApp

Root cause: `Token.initialize()` lacks access control; any caller can run it once and mint the full supply to an arbitrary `launcher` address.

- Vulnerable function: `SmartFlaws/benchmark/AccessControl/ABCCApp/source/contracts/Token.sol:20-27`
- Settings: `SmartFlaws/benchmark/AccessControl/ABCCApp/source/0x422cbee1289aae4422edd8ff56f6578701bb2878_settings.json`
