# STOMPY-2699 spike answer

**INCONCLUSIVE / NOT RELEASE-READY**

project key, team project on MAIN, owner 51/admin. This proves nothing about routed tenants.

**1. Reset and read-back: HELD in the tested MAIN-team scope.** 2 contexts with versions, 1 committed inferred link, 1 ticket with status/body; exact reset and independent delayed full read-back, readiness at four gates, local lock. Both matrix post-cell fixtures matched. Canonical SHA 0f10d861f40120f37e4486413abbd6b3671843bf023bbc6fd19adb6f49d38de0. Point-in-time active-member counts; durable queue identity remains STOMPY-2731; no distributed/deployment lock.

**2. Isolation: HELD in the live smoke.** Lead stompy:1 and one identified teammate stompy:1, no operator MCP servers; isolated HOME/config and allowlisted env. Negative project preflight refused. Matrix-b also retained lead stompy:2 plus one identified teammate with zero MCP calls. No completed comparison row.

**3. Fail-closed: HELD.** Paid kill accepted 1 request, then SIGKILL137; INVALID with null score and unknown terminal cost; orchestrator exit1, 1/4 cardinality. Both real matrix attempts also stopped INVALID/exit1 at 1/4, never a zero-score row. HTTP retries are distinct from zero automatic cell retries.

**4. Frozen task: HELD as a task artifact; difficulty uncalibrated.** One REST-for-MCP lifecycle task at c40570b266df628ed1f5a9260ba77096d8bfe71a, historical sanitized fixture including a pre-agent observed derived edge. No completed solution score; nomemory never launched.

**5. Trusted grader: HELD for the disclosed eight contract oracles.** Pinned networkless grader outside agent; untouched snapshot 8 named failures at exit1, reference 8 passes at exit0, independently verified by Fable. Three critical checks separate from five points. Private-resolver path coupling; real MCP callable and SQL unexecuted; optional bounds and agent test quality unscored. No matrix submission graded because both attempts were INVALID.

**6. Report and comparison: Report generation HELD; n=2 comparison NOT HELD.** Generated reports preserve hashes, build SHAs, costs, actor histograms and all invalid attempts. Matrix-a: 1/4, token cap refusal after16 requests. Matrix-b: 1/4, dollar-reservation refusal after46 requests AND build drift7389ece9 to84e18faa. Zero scored rows, zero nomemory rows, no paired deltas; saturation UNKNOWN.

## Cost

Known terminal-cost subtotal: **$2.65969785** (smoke $0.28939515 + matrix-a $0.61942995 + matrix-b $1.75087275). Paid-kill terminal cost remains unknown.

All-attempt conservative gateway upper bounds: **$6.115312**; remaining of $20: **$13.884688**. Service costs are unmetered; actual total is unknown.

Another unchanged full matrix needs an $18 reservation; only $13.884688 remains. No further paid attempt under the current shape. Review the findings and revise the envelope/deployment window explicitly before continuing.

## B1–B5 shape changes

- **STOMPY-2685 (B1 reset):** Worker drain plus explicit derived-graph manifest and full delayed/post-cell diff are required; readiness scope/active-membership limitation and retained archive history must be visible.
- **STOMPY-2684 (B1 isolation):** Private provider gateway, pinned CLI/API compatibility, per-delegate trace association and lead/every-teammate server histograms; environment isolation alone is insufficient.
- **STOMPY-2700 (B1 fail-closed):** Keep INVALID separate from task failure/zero score, retain killed-run unknown terminal cost and every attempt; non-retryable budget reasons and multiple invalidations (STOMPY-2736).
- **STOMPY-2692 (B3 grader):** Separate contract/private-seam checks from real resolver/MCP/SQL correctness; portable pinned grader; explicit optional-bounds and agent-test-quality coverage.
- **STOMPY-2697 (B5 report):** All-attempt cost ledger, terminal-vs-upper-bound distinction, incomplete matrices and multiple invalidation reasons; paired deltas only for complete valid pairs, no n=2 significance claims.
- **STOMPY-2691 (B2.5 calibration):** Calibrate task/agent token and conservative dollar needs before the fixed n=2 envelope; cached history is not free. Nomemory saturation remains unknown; use fresh holdouts.
- **STOMPY-2694 (B4 release workflow):** Acquire an acknowledged stable deployment window or deployment lock in addition to fixture serialization; server drift invalidates the comparison. Carry global spend reservations and compatibility pins into CI.

## Evidence and validation

Generated attempt reports: [matrix-a](../spike-2699-matrix-a/report.md), [matrix-b](../spike-2699-matrix-b/report.md). [Readiness proof](../spike-2699-readiness/proof.json). [All-attempt ledger](../spike-2699-matrix-b/spend-all-attempts.json).

57 spike tests pass; base/head full-suite failure/error sets identical (existing LongMemEval collection error). Named token-cap RED actually exit1 with dollar-refusal control GREEN; prior isolation, paid-kill, budget, compatibility and readiness RED/GREEN proofs retained. 31 modules <=500 lines, no raised baseline. Skills impact explicitly declared: isolated agent configuration and gateway/readiness workflow, no operator skill file edits.

Backend REST fix #1277 and readiness #1286 are merged and walked on staging through both doors. Benchmark PR #10 remains for Claude review; #9 is its prerequisite. No production changes, key rotation, owner/tier change, app-spec change or tag by Astra.
