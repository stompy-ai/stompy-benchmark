# STOMPY-2699 answer through matrix-c

Outcome: **INCONCLUSIVE / NOT RELEASE-READY**

project key, team project on MAIN, owner 51/admin. This proves nothing about routed tenants.

## 1. Reset and read-back

HELD in the tested MAIN-team scope. 2 contexts with versions, 1 committed inferred link, 1 ticket with status/body; exact reset and independent delayed full read-back, readiness at four gates, local lock. Both matrix post-cell fixtures matched. Canonical SHA 0f10d861f40120f37e4486413abbd6b3671843bf023bbc6fd19adb6f49d38de0. Point-in-time active-member counts; durable queue identity remains STOMPY-2731; no distributed/deployment lock. Matrix-c also held pre/post full fixture and readiness; staging SHA8602947 stayed stable under the confirmed hold.

## 2. Isolation

HELD in the live smoke. Lead stompy:1 and one identified teammate stompy:1, no operator MCP servers; isolated HOME/config and allowlisted env. Negative project preflight refused. Matrix-b also retained lead stompy:2 plus one identified teammate with zero MCP calls. No completed comparison row. Matrix-c lead stompy:3; one teammate trace with zero MCP calls. Histograms retain additional tool-task identities. No operator MCP server observed. Killed run does not prove completed delegation verification.

## 3. Fail-closed

HELD. Paid kill accepted 1 request, then SIGKILL137; INVALID with null score and unknown terminal cost; orchestrator exit1, 1/4 cardinality. Both real matrix attempts also stopped INVALID/exit1 at 1/4, never a zero-score row. HTTP retries are distinct from zero automatic cell retries. Matrix-c timed out at900s/container137 and remained INVALID/null score/null terminal cost; orchestrator exit1,1/4; no retry.

## 4. Frozen task

HELD as a task artifact; difficulty uncalibrated. One REST-for-MCP lifecycle task at c40570b266df628ed1f5a9260ba77096d8bfe71a, historical sanitized fixture including a pre-agent observed derived edge. No completed solution score; nomemory never launched. Matrix-c shows the fixed15-minute wall-clock envelope did not permit completion; task difficulty and nomemory saturation remain uncalibrated.

## 5. Trusted grader

HELD for the disclosed eight contract oracles. Pinned networkless grader outside agent; untouched snapshot 8 named failures at exit1, reference 8 passes at exit0, independently verified by Fable. Three critical checks separate from five points. Private-resolver path coupling; real MCP callable and SQL unexecuted; optional bounds and agent test quality unscored. No matrix submission graded because both attempts were INVALID. Matrix-c was not graded because it lacked a terminal result. Earlier8RED/8GREEN proof unchanged.

## 6. Report and comparison

Report generation HELD; n=2 comparison NOT HELD. Generated reports preserve hashes, build SHAs, costs, actor histograms and all invalid attempts. Matrix-a: 1/4, token cap refusal after16 requests. Matrix-b: 1/4, dollar-reservation refusal after46 requests AND build drift7389ece9 to84e18faa. Zero scored rows, zero nomemory rows, no paired deltas; saturation UNKNOWN. Matrix-c also INCONCLUSIVE1/4:83acceptedrequests,6,160,949tokens,$3.101303 gateway bound, stable build/fixture, fixed900s timeout. No budget refusal observed; no nomemory rows or paired deltas.

## Costs and next decision

Paid kill and matrix-c terminal costs remain unknown; service costs unmetered. Known terminal subtotal remains $2.65969785, gateway bounds total $9.216615. A generated known-cost subtotal of zero for matrix-c is not a free run.

Review STOMPY-2744 wall-clock/task verification calibration. No automatic retry; remaining $15.783385 cannot reserve a fresh $18 matrix. No nomemory saturation or benchmark advantage claim.

## B1–B5 shape changes

- STOMPY-2685 (B1 reset): Worker drain plus explicit derived-graph manifest and full delayed/post-cell diff are required; readiness scope/active-membership limitation and retained archive history must be visible.
- STOMPY-2684 (B1 isolation): Private provider gateway, pinned CLI/API compatibility, per-delegate trace association and lead/every-teammate server histograms; environment isolation alone is insufficient.
- STOMPY-2700 (B1 fail-closed): Keep INVALID separate from task failure/zero score, retain killed-run unknown terminal cost and every attempt; non-retryable budget reasons and multiple invalidations (STOMPY-2736). Record explicit timeout cause while preserving null score and unknown terminal cost (2744/2736).
- STOMPY-2692 (B3 grader): Separate contract/private-seam checks from real resolver/MCP/SQL correctness; portable pinned grader; explicit optional-bounds and agent-test-quality coverage.
- STOMPY-2697 (B5 report): All-attempt cost ledger, terminal-vs-upper-bound distinction, incomplete matrices and multiple invalidation reasons; paired deltas only for complete valid pairs, no n=2 significance claims. Distinguish zero known-cost subtotal from unknown total for timed-out rows.
- STOMPY-2691 (B2.5 calibration): Calibrate task/agent token and conservative dollar needs before the fixed n=2 envelope; cached history is not free. Nomemory saturation remains unknown; use fresh holdouts. Calibrate wall-clock and task verification workload (STOMPY-2744), not only dollars/tokens.
- STOMPY-2694 (B4 release workflow): Acquire an acknowledged stable deployment window or deployment lock in addition to fixture serialization; server drift invalidates the comparison. Carry global spend reservations and compatibility pins into CI.
