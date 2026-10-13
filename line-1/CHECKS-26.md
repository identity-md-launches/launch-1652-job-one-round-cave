# Pepe 26 checks

All **66 tests across six Line 1 suites passed**. Exact commands, exits and test output are in `check-results-26.json`. The new ten-test suite exercises real localhost HTTP transport and guards source attribution, read-method restrictions, URL rejection, redirects, response envelopes, block pinning, calldata identity and recomputed quoter output. The changed ancestor relay test now accepts explicit new loopback ports and still refuses non-loopback HTTP.

The README demonstration completed with **30 local read requests and 11/11 historical quoter matches**, without external network access. A separate real dRPC collection at block **26,186,365** matched the 1-ZTO estimate and saved raw observation and quoter evidence in `tools/zto-refresh/`. PublicNode's pruned-history failures are recorded, not treated as successes.

`delivery-checks-26.json` verifies the goal is byte-identical, all older `dist/line-1/` files are byte-identical, only one numbered record was added, the artifact URL is the wall SHA-256, both PNGs are identical 1254-square images, and the JPEG is 512-square and below 100 KB. Required images remain untracked. Changed files are within the permitted paths; no changed non-artifact file exceeds 100 KB. `git diff --check` passed. No configuration or dependency directory was changed.

The composited wall and JPEG were visually inspected. The ancestor pixels outside the small addition rectangle are exact, and no unmet visual requirement was observed. These checks are local contributor evidence, not independent certification or a guarantee of future execution or price.
