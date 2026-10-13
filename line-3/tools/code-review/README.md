# Code Review

Check that proved Ethereum code still matches a separately reviewed identity before another worker relies on it. This offline gate compares the **entire ordered runtime/proxy path**, including every address, runtime Keccak hash, recognized proxy kind, next address, and both measured EIP-1967 slots. It re-verifies the raw state proofs on every run and enforces an explicit maximum age in blocks. It makes no network request and never creates a transaction.

One command from the repository root shows it working on **real saved ZTO first, then IMD proofs**, without inventing an independent trust anchor:

```sh
python3 -B line-3/tools/code-review/demo.py
```

Expected: `demonstration_passed: true`. Both real identities match their example review documents, but the gate correctly refuses them with `missing-caller-anchor`. A third case adds `code-evidence-too-old` when the reference height is one block beyond the example age limit. The demonstration exits 0 only when these expected outcomes hold. It does not contact the chain or pretend the historical evidence is current.

Requires Python 3.9+ and only the standard library. Retain the committed sibling folders `code-ancestry`, `code-proof`, and `code-lens` (including Keccak). No installation, configuration change, account, wallet, network, or external package is required. The demo also needs their saved evidence JSON files.

## What happened when tried

The ZTO and IMD raw proofs at Ethereum block **26,185,280** both reverified, and their full identities matched. At the example reference block **26,185,288**, age was eight blocks and the sole refusal was the missing caller anchor. At reference height **26,185,289**, the eight-block age limit additionally refused the evidence. `zto-result.json` and `imd-result.json` record the first two results; `demo-result.json` records the runnable demonstration.

Nineteen adversarial tests passed, covering wrong addresses despite identical hashes, changed review hashes/slots, proof corruption, consistent-looking forged code, path truncation, duplicate addresses, age boundaries, malformed/extra review fields, JSON duplicate keys, workspace escapes, CLI exit behavior, and unproven beacon routing. The existing eight real descendant headers also passed through the gate: linking to a newer checkpoint **does not refresh the age of the original code evidence**. Tests exercise explicit hash matching with an observed hash; that does not certify its independent authenticity.

## Use with your own reviewed identity

`zto-review.json` and `imd-review.json` are **demonstration data copied from the historical observations**, not audited code approvals. Their eight-block limit is an example, not a recommendation. For actual use, supply a document containing the addresses, hashes, ordered path, slots, and age limit you have independently chosen and reviewed. The CLI deliberately has no “trust this observation” or wildcard option.

The review document has exactly `schema` (`code-review-v1`), `chain_id` (integer 1), `target`, `path`, and `max_age_blocks` (nonnegative integer). Each path entry has exactly `address`, `code_hash`, `kind`, `next_address`, and `storage` with `implementation` and `beacon` 32-byte words. Those words may genuinely be zero when the measured slot is empty; they are evidence, never placeholder addresses. The saved review documents show complete real examples. Unknown fields, duplicate JSON keys, cyclic/disconnected paths, and malformed values are refused.

Run the generic CLI with workspace-local files:

```text
python3 -B line-3/tools/code-review/code_review.py --bundle YOUR_PROOF.json --review YOUR_REVIEW.json --as-of-block DECIMAL_REFERENCE_HEIGHT --anchor-hash INDEPENDENT_EXECUTION_BLOCK_HASH
```

The uppercase arguments describe caller inputs; they are not runnable stand-ins. No unknown address or anchor is filled in. The anchor must match the proved code block. To anchor through a later checkpoint, also pass `--ancestry YOUR_ANCESTRY.json`; the hash must then match that file's final checkpoint. Obtain anchor authenticity independently. Evidence and review files cannot grant themselves trust through embedded flags. `--as-of-block` is a caller-supplied height, not a wall-clock/latest-block check, and must be at least the checkpoint height.

| Exit | Meaning |
| --- | --- |
| 0 | Exact reviewed identity, age, proven routing inputs, and separately supplied anchor hash all match. |
| 3 | Valid evidence, but one or more review requirements refuse it; structured reasons on stdout. |
| 1 | Invalid/malformed evidence or review, wrong anchor, or input error; no partial success JSON. |
| 2 | Invalid CLI syntax (argparse). |

An absent anchor always refuses. A beacon path always refuses because Code Proof does not prove the beacon `implementation()` call result. EIP-1967 implementation entries remain **candidates**: proven slot contents do not establish that bytecode uses those slots. Accepting a reviewed identity does not prove routing semantics, semantic safety, finality, consensus, anchor authenticity, continuously unchanged code, current code, or permission to transact. A caller who trusts an attacker-provided review/hash/height defeats its own trust boundary; the gate cannot independently repair those choices.

The output includes a Keccak fingerprint of the normalized review, exact evidence/checkpoint heights, age, differences, source attribution, and explicit trust limits. It never treats a previously saved verdict as evidence.

Run the focused checks:

```sh
python3 -B -m unittest discover -s line-3/tools/code-review -p 'test_*.py' -v
```
