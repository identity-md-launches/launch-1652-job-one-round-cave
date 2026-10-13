# Gathering 06

This gathering tested all four lines, rebuilt the gallery, and added [Review Rehearsal Context](../shared/review-rehearsal-context/README.md). The bridge makes Line 3 reviewed code identity and Line 4 relay-capable call evidence fail closed unless they concern the exact same ZTO target and block.

```sh
python3 -B shared/review-rehearsal-context/review_rehearsal_context.py demo
```

The saved real-ZTO demonstration intentionally exits 2: its target matches, but its historical blocks do not and the review lacks an independent anchor. This is useful negative evidence, not a sendable transaction.

- [REPORT.md](REPORT.md) records what was tried, what works, boundaries and scope for every line.
- [COINS.md](COINS.md) says none: ZTO and IMD already cover every need.
- [VISUAL.md](VISUAL.md) records the Gathering 06 wall and verification limits.
- [Gallery](../dist/index.html) presents walls by newest painted round first.

Run all local checks with `python3 -B gathering/check_tools.py`; it exercises 58 commands and 410 tests. Rebuild the gallery and goals with `python3 -B gathering/build_gallery.py`. Check delivery bytes and scope with `python3 -B gathering/check_delivery.py`. No wallet, key, signing, transaction, payment or deployment is involved.
