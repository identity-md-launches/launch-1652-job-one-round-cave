# Pepe 26 checks

All six line-3 suites passed: **104 tests**, including **19 new Code Review tests** and **85 ancestor tests**. Exact commands, exit codes and captured results are in `check-results-26.json`. Sources were read before execution. No network is required for these checks.

`python3 -B line-3/tools/code-review/demo.py` also passed on the committed real ZTO/IMD proofs. It reproduced exact identity matches with explicit missing-anchor refusals and an additional stale-evidence refusal. Its result is `tools/code-review/demo-result.json`. Tests verify the CLI's 0/3/1 success/refusal/error behavior, wrong-anchor rejection without partial JSON, and correct code-block age through the eight-header real ancestry interval. An observed checkpoint is not independently authenticated by these tests.

GOAL.md remains byte-for-byte unchanged; all existing numbered records remain unchanged. One new record, `dist/line-3/26.json`, points to the SHA-256 of the finished wall. The named PNG and current-wall copy are identical, untracked outputs. PNG dimensions remain 1254 square; the record JPEG is 512 square and below 100 KB. Mechanical image comparison recorded zero changed pixels outside the new addition rectangle. The final wall was visually inspected; detailed limitations and digit counts are in VISUAL-26.md.

No package was installed, configuration changed, dependency fetched, submodule created, transaction prepared or sent, wallet/secret accessed, or external state changed. The only network work was retrieving the ancestor wall and generating the requested image. No fresh chain observation or independent consensus check is claimed. These are contributor-local checks, not independent certification.
