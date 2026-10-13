# Relay Rehearsal

Rehearse a real Ethereum contract call through an explicitly supplied contributor
loopback relay. This repairs the transport refusal reported for Line 4 in
`gathering/REPORT.md`. Python 3.9+ and the standard library are sufficient; no
installation, account, environment settings or wallet access is needed.

Run from the repository root:

```sh
python3 -B line-4/tools/relay-rehearsal/relay_rehearsal.py demo
```

This command works offline. It validates and decodes the committed real ZTO
`totalSupply()` observation, including the explicit relay provenance. Copy both
this folder and its sibling `call-rehearsal/` to reuse it elsewhere.

For a fresh read-only collection, replace `<port>` with the current worker-provided
Ethereum relay port:

```sh
python3 -B line-4/tools/relay-rehearsal/relay_rehearsal.py live --relay 'http://127.0.0.1:<port>/rpc/1' --save line-4/tools/relay-rehearsal/new-observation.json
```

There is no remembered port or automatic discovery. ZTO is the default; use
`--token IMD` for IMD. The original CLI now also accepts `--relay` in its `demo`,
`call` and `transfer` modes, so custom calls retain their required explicit public
sender, target and calldata. The relay is only a transport: chain ID must still be
Ethereum mainnet, code must exist, both code and call use one finalized block hash
with `requireCanonical: true`, and the header must remain unchanged afterward.

Only `http://127.0.0.1:<port>/rpc/1` is accepted as a relay. Invalid ports, other
hosts, credentials, queries, fragments, alternate chain paths and redirects are
refused. The four inherited read-only JSON-RPC methods remain the entire
allowlist. Proxy discovery is disabled. The transport never reads environment
variables, keys or files outside the workspace, signs, submits transactions,
pays, or deploys contracts. RPC response bytes and request duration retain the
ancestor's bounds. No public fallback is attempted by this tool.

`--rpc` chooses public attribution, defaulting to
https://ethereum-rpc.publicnode.com. It does not establish the relay's upstream
provider identity. Saved observations include `transport.kind: contributor-relay`,
`source_is_attribution_only: true` and `independent_provider_verified: false`.
They omit the local endpoint. Reports retain these flags and explain their limits.
Do not count differently attributed calls through one relay as independent
witnesses. Older strict Call Changes/Witness/Expectation validators reject the
additional `transport` field; use this demo or the updated Call Rehearsal replay
to inspect relay observations, rather than deleting provenance to force acceptance.
Existing observations and the older tools continue to work unchanged.

## What happened when tried

The live command used this assignment's contributor relay. At finalized Ethereum
block **26,186,493**, hash
`0x8aa88009bea17fb98fdb651575354f6540698f8377010ba30ef907e9d2499bcb`,
ZTO `totalSupply()` returned **1000000000000000000000000000** base units.
The actual observation is `zto-relay-observation.json`; its offline replay exits 0.
Public source attribution is https://ethereum-rpc.publicnode.com, with upstream
identity explicitly unverified. No transaction was submitted.

Ten focused tests pass, covering routing, URL refusal before opener creation,
dynamic ports, read-only method restrictions, redirect refusal, direct transport
compatibility, provenance flag validation, saved real evidence and offline replay.
All 87 inherited Line 4 tests also pass, for **97 tests total**.

```sh
python3 -B -m unittest discover -s line-4/tools/relay-rehearsal -p 'test_*.py' -v
```

Return categories and exit codes are inherited: returned/true = 0, false/revert = 1,
unexpected ABI/RPC/input failure = 2. A matching supply return is a historical
provider observation, not a receipt, gas estimate, state diff, authenticated
chain proof or promise about future execution.
