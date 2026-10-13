# Pepe 26 checks

All checks ran from the repository root, using only standard-library Python for
the delivered tool. Execution profile is none; no Foundry configuration or
Solidity files were introduced.

The following five commands passed, with 20, 36, 8, 23 and 10 tests respectively:

```sh
python3 -B -m unittest discover -s line-4/tools/call-rehearsal -p 'test_*.py'
python3 -B -m unittest discover -s line-4/tools/call-changes -p 'test_*.py'
python3 -B -m unittest discover -s line-4/tools/call-witness -p 'test_*.py'
python3 -B -m unittest discover -s line-4/tools/call-expectation -p 'test_*.py'
python3 -B -m unittest discover -s line-4/tools/relay-rehearsal -p 'test_*.py'
```

The new tool's `demo` exits 0 offline. A live ZTO supply rehearsal through the
assignment's contributor Ethereum relay also exited 0 at block 26,186,493. Saved
evidence records public attribution and unverified upstream identity, omitting
the machine-local endpoint. Only read-only JSON-RPC methods were used.

The PNG and JPEG structural inspectors passed. The original wall's SHA-256 was
verified before editing and again before patch assembly. The finished wall
keeps its original 1254-square dimensions; decoded RGB pixels outside the
addition rectangle are identical to the original. The JPEG is 512-square and
below 100 KB. Record 26 has the required six attributes and exact image hash.
GOAL.md, every older record and every file outside allowed paths are unchanged.
Both wall PNG paths are left untracked for artifact upload. Detailed local
measurements are in `delivery-checks-26.json`.
