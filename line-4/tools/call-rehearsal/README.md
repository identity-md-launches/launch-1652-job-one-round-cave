# Call Rehearsal

Rehearse an Ethereum contract call before deciding whether to submit it. The tool uses only Python 3.9+ standard-library modules. It never opens a wallet, reads environment variables, signs, broadcasts, or changes on-chain state. No installation is needed.

Run this from the repository root to see a real ZTO observation decoded **offline**:

```sh
python3 -B line-4/tools/call-rehearsal/rehearse.py replay line-4/tools/call-rehearsal/zto-observation.json
```

It prints the target, calldata, pinned block, raw return and decoded integer. The supplied observation is a real `totalSupply()` call, not a fabricated fixture. To rehearse it against live Ethereum:

```sh
python3 -B line-4/tools/call-rehearsal/rehearse.py demo
```

ZTO is the default; `demo --token IMD` uses IMD. Add `--save` followed by a new workspace-relative JSON path to retain the result; existing files are never overwritten. Both supplied public endpoints are supported through `--rpc`. An endpoint that does not support hash-pinned calls fails explicitly; there is no silent fallback to a different block.

For a worker-provided relay, `demo`, `call` and `transfer` now accept an explicit
`--relay 'http://127.0.0.1:<port>/rpc/1'`. `--rpc` remains public source attribution.
Relay observations retain additional provenance flags and do not claim verified
upstream identity. See [Relay Rehearsal](../relay-rehearsal/README.md) for an offline
real-ZTO demo, transport checks and compatibility limits for older strict validators.

## Your own proposed call

`call` requires `--to`, `--sender` and `--data`. Supply actual public addresses and even-length hexadecimal calldata. `--value` is an optional unsigned decimal amount of native ETH in wei, default zero. `--returns raw|uint256|bool` selects the interpretation; it defaults to raw bytes. The tool does not infer an ABI or treat an unknown return as a payment receipt.

`transfer` constructs and rehearses an ERC-20 `transfer(address,uint256)` call. It requires your actual `--sender`, intended `--recipient` and decimal `--amount` in token **base units**, with `--token ZTO|IMD` defaulting to ZTO. It expects a canonical ABI boolean. No address is filled in for you. Run `transfer --help` to see the options. A simulation can name a public sender without possessing its key; that does not establish control of that sender. Nothing is submitted.

Every rehearsal checks mainnet chain identity, fetches a finalized block, confirms that the target has runtime code, and uses the same block hash with `requireCanonical: true` for `eth_getCode` and `eth_call`. It rechecks the block header afterward. The only other allowed RPC methods are `eth_chainId` and `eth_getBlockByNumber`. HTTP JSON-RPC requests carry a tool-specific User-Agent; redirects and environment proxy discovery are disabled.

## Results

| Result | Exit | Meaning |
| --- | ---: | --- |
| `returned` / `returned_true` | 0 | Call returned under the selected interpretation. |
| `reverted` / `returned_false` | 1 | Provider reported a revert, or ERC-20 returned false. |
| `unexpected_return` / `inconclusive` | 2 | Return did not fit the selected ABI type, or RPC could not determine execution. |
| Input, transport or consistency error | 2 | JSON error on stderr; no successful rehearsal claimed. |

Revert data, when supplied, is decoded as `Error(string)` or `Panic(uint256)`; other selectors stay raw. Missing revert bytes stay missing. RPC failures such as unavailable historical state are not relabeled as EVM reverts. An empty result is accepted only in raw mode; it is not accepted as a boolean or uint256. Individual hex data is bounded to 32 KiB, RPC responses and saved observations to 90 KB, and each network request to 25 seconds. Files supplied to the CLI must resolve inside the current workspace.

## What happened when tried

- ZTO `totalSupply()` at finalized Ethereum block **26,183,845** returned **1000000000000000000000000000** base units. Stored in `zto-observation.json`.
- IMD `totalSupply()` at block **26,183,877** returned **4174659238000000000000000** base units. Stored in `imd-observation.json`. Its runtime exposed an initial 16 KiB code-size cap; raising the bounded limit to 32 KiB fixed that failure.
- A deliberately unsupported selector `0xffffffff` on ZTO at block **26,183,877**, with the supplied public IMD contract address as the simulated caller, returned RPC code 3, `execution reverted`, and no revert bytes. Stored in `zto-revert-observation.json`. This is a negative probe, not an attempted payment or a claim that IMD is the user's account. Replaying it exits 1 as intended.
- Twenty offline unit tests pass, including hash pinning, changing blocks, wrong chains, false/empty returns, missing code, malformed RPC envelopes, revert decoding, bounded data, CLI exit codes and the saved real observation.

```sh
python3 -B -m unittest discover -s line-4/tools/call-rehearsal -p 'test_*.py' -v
```

The unit tests label synthetic RPC branches explicitly. Live observations are provider reports, not cryptographic evidence. Offline replay checks structure and reinterprets results; it does not authenticate a provider or reconstruct Ethereum state. A finalized historical simulation is not a forecast of inclusion: balances, allowances, contract state and caller context can change. This version does not estimate gas, model pending transactions, produce state diffs, or prove that a successful boolean caused the intended token movement. Contracts with nonstandard empty ERC-20 returns produce `unexpected_return`.

## Artifact helper

`thumbnail.py` is a separate standard-library PNG reader and baseline JPEG encoder used to produce this round's required thumbnail. It reads only `artifacts/line-4/wall.png` and writes `dist/line-4/01.jpg`; it is not imported by Call Rehearsal. It accepts opaque, non-interlaced 8-bit RGB/RGBA PNG, checks PNG chunk CRCs, averages pixels down to 512 square, and emits a three-component JPEG. Run `python3 -B line-4/tools/call-rehearsal/thumbnail.py` from the root to reproduce the thumbnail. No downloaded library or executable is required.

Protocol references: [Ethereum JSON-RPC](https://ethereum.org/en/developers/docs/apis/json-rpc/), [EIP-1898 block-hash parameters](https://eips.ethereum.org/EIPS/eip-1898), and [ERC-20 return values](https://eips.ethereum.org/EIPS/eip-20).
