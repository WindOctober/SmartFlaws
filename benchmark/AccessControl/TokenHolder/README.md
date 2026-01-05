# TokenHolder

Root cause: missing whitelist checks in `BorrowerOperationsV6.buy()` allow user-controlled `whitelistedDex` and `inchRouter`, so `approve` and `address.call` targets are arbitrary.

- Affected function: `benchmark-defihacklabs-2025/contracts/20251007_TokenHolder/src/BorrowerOperationsV6.sol`
- Local copy: `smart-contract-flaw/benchmark/AccessControl/TokenHolder/src/BorrowerOperationsV6.sol`
