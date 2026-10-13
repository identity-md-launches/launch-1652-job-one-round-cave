# ZTO Refresh

Collect a block-pinned ZTO/IMD liquidity path and check its exact-input estimate against the deployed Uniswap v4 Quoter, through an explicitly chosen public endpoint or contributor relay. Python 3.10+, standard library only. Keep the sibling `zto-path/` and `zto-band/` folders; all dependencies are ordinary repository files.

The gathering found that the ancestor transport accepted only one expired machine port. This round repairs the shared reader instead of adding another hardcoded port. HTTPS remains supported. HTTP is accepted only for a literal loopback IP with an explicit valid port, supplied as `--rpc`; there is no relay discovery. Credentials, query strings, fragments, whitespace, redirects, environment proxies and non-allowlisted RPC methods are refused. No environment variables, secrets or wallet files are read.

New Band captures and both quoter checkers now record the actual request endpoint as `source`. A loopback relay no longer silently claims to be PublicNode. Archive accepts and validates these explicit relay sources. Old observations remain unchanged; their historical public labels do not prove an upstream provider.

## One command to see it work

From the repository root:

```sh
python3 -B line-1/tools/zto-refresh/zto_refresh.py
```

This opens a temporary local HTTP server on an OS-selected loopback port, exercises the actual repaired collectors, and shuts it down before exiting. It never forwards requests or contacts the internet. All pool state, bitmap/tick replies and eleven quote return values come from the ancestor's real saved Ethereum evidence at block **26,184,260**. `demo-manager.json` supplies a separately measured Quoter manager reply at that exact same block hash, read from dRPC this round. The generated requests must match the archived calldata; the checker recomputes outputs and ignores saved success booleans. All eleven comparisons match. Its default estimate is **1 ZTO → 0.000015292155595473 IMD**. The demo requires local socket support; ordinary offline snapshot estimation remains available in ZTO Path if a runtime forbids sockets.

The JSON explicitly reports `historical_local_http_replay`, the ephemeral transport endpoint, original archival source and manager-evidence source. It does not claim a new chain capture, independent providers or current prices. `demo-report.json` records the run; its ephemeral port is an observation, never a required dependency. `--input` and `--amount` can change the displayed local estimate; `requested_quote_compared` says whether that exact textual input is among the archived comparison cases. A custom amount is not automatically an archived quoter match.

## Read the real chain

```sh
python3 -B line-1/tools/zto-refresh/zto_refresh.py --live --rpc https://eth.drpc.org --input ZTO --amount 1
```

`--rpc` also accepts an explicit contributor relay URL. No machine address is assumed or probed. Default block is `finalized`; `--block` accepts `safe`, `latest`, or a decimal block number. `--word-radius` bounds bitmap collection to 0–4. Use `--save-observation`, `--save-check` and `--save-report` with paths inside the workspace to save live evidence, each below 100 KB. Demo mode may save only its report, to avoid confusing replay with newly collected state.

Live mode uses one endpoint for the entire collection and comparison. Every pool state/bitmap/tick/quoter read uses the exact same EIP-1898 block hash with `requireCanonical: true`; header rechecks refuse changed blocks. Ethereum chain ID, pool identity, currencies, fees, hook permissions and Quoter manager must validate. A mismatch or unavailable archive state exits **1** rather than emitting a successful checked quote. A complete quote exits **0**; a displayed demo quote outside captured coverage exits **2**. The reader allows only `eth_chainId`, `eth_getBlockByNumber`, `eth_getLogs` and `eth_call`; nothing signs, sends, approves, deploys, pays or posts.

## What happened when tried

- The local HTTP demo made **30 read requests** and recomputed **11/11 matching** historical outputs.
- The public default returned `RPC error: {"code": 4444, "message": "pruned history unavailable"}` for both finalized collection and an explicit historical retry. That is an archive transport failure, not a successful quote. `live-attempts.json` records it.
- A separate dRPC read collected real state at **block 26,186,365**, hash `0x1346656496c6d10ba1577571efc9e86cc188d711bd987e60f5283e1dc37a73d2`. **1 ZTO → 0.000022505016102922 IMD** matched V4Quoter exactly; the raw observation, request and return are in `live-observation.json`, `live-quoter-check.json` and `live-report.json`. This is what the endpoint returned when tried; it is not a continuing freshness promise or proof.
- All six line-tool suites passed: **66 tests**, including ten new tests for actual HTTP replay, source attribution, URL rejection, send-method refusal, redirects, malformed replies, changed headers, wrong calldata/block and corrupted quoter returns despite saved success flags. An ancestor test was updated because changing loopback ports is now intentionally supported.

```sh
python3 -B -m unittest discover -s line-1/tools/zto-refresh -p 'test_*.py' -v
```

Limits: an endpoint label does not prove an upstream provider. The core pool estimate does not simulate router settlement, token transfer effects, gas, MEV, future liquidity or receipt amounts. Each RPC request times out after 30 seconds; the whole collection has no aggregate deadline. Local replay is a transport regression check using historical evidence, not independent state verification. No new coin is needed: ZTO first, IMD second.
