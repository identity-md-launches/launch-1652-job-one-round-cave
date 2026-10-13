# Draft Witness

Verify that one unsigned ERC-20 `approve(spender, 0)` draft is *exactly* one of the optional candidates derived from reviewed ZTO permission evidence and policy. It gives a worker a final offline integrity check before presenting a draft to its owner. Python 3.10+ and the standard library are sufficient; it reuses the adjacent Approval Draft and Permission Gate validators already in this line.

## One command to see it working

From the repository root:

```sh
python3 -B line-2/tools/draft-witness/draft_witness.py
```

The local demonstration recreates the first of three historical ZTO owner-review candidates from the bundled real inventory, then returns `"status": "exact_match"` and `"matches_reviewed_draft": true`. It performs no network request and saves nothing.

## What happened when tried

The bundled observation at Ethereum block **26,184,897** has 19 measured ZTO owner–spender pairs. The existing deny-all review identifies three positive permissions, including two on empty balances. Draft Witness accepted each structurally identical candidate. Four local tests also confirmed that one changed calldata nibble, an added `gas` field, and evidence outside the chosen policy interval cannot obtain a match.

## Check an external draft object

Supply all three inputs from within the current workspace:

```sh
python3 -B line-2/tools/draft-witness/draft_witness.py --draft path/to/draft.json --observation line-2/tools/permission-gate/live-observation.json --policy line-2/tools/permission-gate/demo-policy.json
```

`draft.json` must contain exactly one candidate object emitted by Approval Draft. This tool compares the complete object, including its ZTO contract target, owner, spender, zero-value field, and `approve(spender, 0)` calldata. Any extra transaction field (including nonce, gas, or fee), different destination, owner, spender, calldata, or evidence/policy result fails. A mismatch exits 3; invalid files exit 1.

A match is deliberately narrow: it is not an owner instruction, signature, transaction simulation, broadcast, payment, or confirmation. Evidence is historical and incomplete; refresh canonical state and let the account owner decide and verify independently before any action. Known pairs do not cover unknown spenders, Permit2 permissions, unused signatures, custom authorizations, other tokens, or chains.

Run the tests:

```sh
python3 -B -m unittest discover -s line-2/tools/draft-witness -p 'test_*.py' -v
```
