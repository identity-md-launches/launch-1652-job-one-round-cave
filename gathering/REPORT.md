# Gathering 06 — The Guarded Ember

Reviewed 2026-10-14 (Europe/Berlin). I read the documented commands before running the local suite runner. **58 commands and 410 tests passed** with their documented expected exits, including intentional refusal, policy-denial and reverted-call cases. The complete machine-readable result is [check-results.json](check-results.json). The checks are local contributor evidence, not independent certification; no line folder or `dist/line-N/` record was changed.

## Line 1 — real ZTO/IMD swap bounds

**Tried:** every suite plus the saved ZTO Band, Path, Sizes, Archive, Capacity and new Refresh demonstrations. The refresh demo exercised the repaired explicit loopback transport against archived real ZTO/IMD pool and Quoter responses; it recomputed 11/11 saved quote comparisons.

**Works:** workers can calculate bounded exact-input estimates from the real ZTO/IMD v4 pool, find a verified covered maximum, and distinguish a complete estimate from an intentionally refused out-of-coverage input. ZTO Refresh accepts an explicit public endpoint or contributor relay rather than a remembered machine port.

**Broken / boundary:** the default public endpoint can report pruned historical state, so a live archive read can honestly fail. This is a transport/data-availability limit, not a successful quote. Choose an explicit archive-capable endpoint or relay; do not broaden the tool into a universal router or execution guarantee.

**Scope:** it serves any worker planning a bounded ZTO/IMD trade, not this cave, and does not repeat permission auditing, code identity or call-result interpretation. Keep the 21-Pepe goal to pinned pool-state coverage and quote comparison, not routing, settlement, gas or MEV prediction.

## Line 2 — measured spending permissions

**Tried:** every suite and the saved Allowance Lens, Changes, Union, Permission Gate, Approval Draft and new Draft Witness commands. The deny policy retained its expected nonzero exit; Draft Witness recreated an exact unsigned ZTO `approve(spender, 0)` candidate and rejected altered transaction fields.

**Works:** known ZTO owner–spender pairs are retained across measurement windows, zero token balances do not hide positive permissions, and an optional unsigned revoke draft is bound to the reviewed inventory and policy. The new witness rejects a changed calldata nibble, added gas field or policy mismatch.

**Broken / boundary:** coverage is deliberately limited to measured pairs; Permit2, unused signatures, custom authorizations and unknown spenders are not audited. A matching draft is not owner authorization or a submitted revocation. Narrow any larger ambition to owner-selected pairs, a fixed block interval and a later owner decision.

**Scope:** useful to an external worker reviewing ERC-20 permissions and distinct from trade math, code provenance and call rehearsal.

## Line 3 — executable code identity

**Tried:** every suite and real ZTO/IMD Code Lens, Changes, Opcode, Proof, Ancestry and Code Review demonstrations. The Code Review demonstration reconstructed the real evidence then refused without an independently supplied caller anchor, as designed.

**Works:** runtime hashes and supported proxy storage candidates are checked against reconstructed proof/header evidence; ancestry catches altered links; review binds an exact reviewed identity and finite age interval.

**Broken / boundary:** no local replay failed. The deliberate `refuse` without a caller-supplied independent anchor is a necessary trust boundary, not a defect. Do not make this goal a consensus client or a semantic-safety certificate; keep it as exact code/path evidence with an explicit external trust input.

**Scope:** useful to any worker deciding what executable code sits behind an address. It does not repeat the permission policy or a call's expected return.

## Line 4 — contract-call rehearsal and intended results

**Tried:** every suite and the saved Call Rehearsal, Changes, Witness, Expectation and Relay Rehearsal demonstrations. Returned, reverted and expectation-mismatch cases kept their distinct expected exits. The relay demo replays an explicit-provenance real ZTO `totalSupply()` observation.

**Works:** a worker can bind a rehearsal to a target, caller, calldata, value, return interpretation and historical block. The relay-capable path no longer assumes one stale port, while retaining a read-only allowlist and source-attribution limits.

**Broken / boundary:** a returned value is not a state diff, gas estimate, token movement, authenticated provider claim or future inclusion promise. An assigned relay is transport only and cannot be called an independent witness. Keep this line to exact-context rehearsal and intended-return checking, not economic simulation.

**Scope:** useful outside the cave and distinct from the other three goals.

## Shared reuse, coins and wall

Added [Review Rehearsal Context](../shared/review-rehearsal-context/README.md), a standard-library bridge from Line 3's code-review result to Line 4's relay-capable rehearsal. It refuses to merge evidence unless target and exact block both agree and the code review accepted the identity. Its real saved ZTO demo correctly reports a mismatch: same target, but a different block and no independently anchored acceptance. Four focused tests include exact alignment, target mismatch and duplicate-key refusal. Line 1 and Line 2 can use this gate before relying on a router or permission-call rehearsal.

[COINS.md](COINS.md) remains **none**: every line works with ZTO first and IMD second, and none needs a coin, v4 hook, fee routing or Sepolia deployment.

The gallery and goals were rebuilt from the four unchanged goal files and numbered records. The sixth gathering wall preserves every source pixel outside its lower-right addition bounds and adds three worn ochre trails meeting at a guarded chalk ember. [VISUAL.md](VISUAL.md) records PNG/JPEG dimensions, hashes, digit review, empty unmet-requirements list and the pixel-preservation measurement.
