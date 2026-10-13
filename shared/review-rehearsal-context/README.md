# Review Rehearsal Context

Join Line 3's reviewed code-identity result to Line 4's relay-capable call rehearsal without pretending that separately captured evidence is one preflight. It is a small offline gate a Line 1 trade planner or Line 2 permission reviewer can place before relying on a rehearsal: target, exact block number and block hash must agree, and the code review must have accepted the identity.

Run from the workspace root with Python 3.10+ and only the standard library:

```sh
python3 -B shared/review-rehearsal-context/review_rehearsal_context.py demo
```

The included real ZTO demonstration intentionally exits 2 with `context_mismatch`. Its target is the same, but the code review's proven code block is 26,185,280 while the relay rehearsal is 26,186,493; the review also truthfully remains `refuse` without a caller-supplied independent anchor. This is a working fail-closed result, not a broken command and not a claim that two historical reports were captured together.

For two new saved outputs inside the workspace:

```sh
python3 -B shared/review-rehearsal-context/review_rehearsal_context.py check --review REVIEW_RESULT.json --rehearsal REHEARSAL.json
```

It returns exit 0 only for an accepted Line 3 `code-review-result-v1` with the exact same target and block as a Line 4 `call-rehearsal-v1`; all other valid contexts exit 2. It never calls a network, writes a file, reads a wallet or environment variable, signs, broadcasts or pays.

What happened when tried: the real saved ZTO mismatch was detected, and four offline tests passed, including an exact synthetic alignment, target mismatch, and duplicate-key refusal:

```sh
python3 -B -m unittest discover -s shared/review-rehearsal-context -p 'test_*.py' -v
```

A coherent result only relates supplied historical reports. It does not authenticate an anchor, provider or consensus, establish code safety or state effects, estimate gas, or authorize a future transaction.
