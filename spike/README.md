# STOMPY-2699 staging shadow spike

This is an incomplete release-gate spike, branched from `4ec5ffb` (PR #9).
The committed preflight report is **INCONCLUSIVE**. It is not a benchmark win,
production gate, or routed-tenant result. See STOMPY-2711: background entity
extraction recreated an inferred graph edge after an exact reset. The manifest
now explicitly includes that one edge from the retained c40570b2 preflight proof,
observed before any paid agent ran. Stable replay with readiness subsequently held; the two paid matrices remain INVALID.

The fixture identity is **project key, team project on MAIN, owner 51/admin**.
It proves nothing about routed tenants. All fixture traffic uses staging MCP.
The harness never mints, rotates, revokes or deletes a project key.

## Run

Use Python 3.11+, Docker, and `pip install -r spike/requirements.txt` in an
isolated environment. The three local base images must match `spike/images.json`.
`python -m spike.build_image` verifies them and builds the agent runtime. The
trusted grader is the immutable image ID in `spike/grader.py`; it must already
exist locally. Registry distribution of this private dependency image is a B3
follow-up, not claimed portable by this spike.

Provide `STOMPY_BENCHMARK_PROJECT=stompy_benchmark` and
`STOMPY_BENCHMARK_API_KEY` through the operator-approved local environment or CI
secrets. The operator already holds those values in
`~/.config/stompy/benchmark.env`. The harness only reads environment variables.
Provider access uses only the expressly authorized 1Password field
`op://Stompy/stompy-prod/ANTHROPIC_API_KEY_STOMPY_BENCHMARK`.
`start_gateway.sh` sources `~/.config/stompy/op.env`, reads that field into a
shell variable, and sends it over stdin to a private model gateway container.
It never writes a credential file or puts the provider key in Docker Config.Env.
The agent shares only the gateway's network namespace and receives a loopback
URL plus a non-secret local placeholder token. Provider keys, vault tokens,
operator login/configuration and gateway mounts are absent from the agent.
The grader and publisher get no provider credential.

The gateway permits only pinned Sonnet message/count-token requests. It
serializes reservations before billable requests, caps tokens and dollars,
rejects premium/server-tool requests, and retains the reservation on unknown
billing. The CLI's own budget is a second limit. Its 240-second API timeout exceeds
the gateway's 180-second upstream timeout; streaming responses are buffered. A killed stream's cost remains
unknown even when its conservative reservation is known. The separate Docker
control uses a dummy stdin key and makes zero upstream calls. For the compatibility.py-pinned
CLI 2.1.296 / Anthropic API 2023-06-01 pair, unsupported adaptive-thinking display values become `omitted`;
server `context_management` is removed and the full supplied history is counted
and sent. Fixture MCP traffic is paced below existing fallback limits; refused
calls are never silently retried.

Governance decision: this harness lives in the separate `stompy-benchmark`
repository, outside dementia-production's scanned source tree. No backend
subprocessor gate or manifest is weakened. Only our own repository source and
the committed historical engineering fixture may reach the provider; never
customer corpora. Publishing a CI secret remains Markus's step.

```sh
python -m spike.smoke --output runs/spike/unique-isolation-smoke
python -m spike.run --gen unique-name --backend /path/to/dementia-production
python -m spike.run --gen unique-kill-control --backend /path/to/dementia-production --kill-control
```

Normal schedule: Sonnet `stompy/1, nomemory/1, nomemory/2, stompy/2`; maximum
$4.50 per cell, $18 reserved total, no automatic retries. The separate killed
control reserves $0.25 and kills after ten seconds once an upstream request
has been accepted. The separate isolation smoke reserves $1.25. A shared locked
ledger at `/private/tmp/stompy-2699-spend.json` caps all attempts together at $25 (Markus, 2026-10-11);
unknown attempts keep their reservation. Never delete it to regain budget.
The top-up preserves the prior $6.115312 upper bounds, leaving $18.884688;
never reprice or remove historical attempts. Worker/embedding costs are
not metered, and killed processes may lack a terminal billing total; reports
preserve unknown costs. Do not describe the reserved amount as actual spend.
Output generations are append-only under ignored `runs/spike/`.

The fixed local advisory lock covers reset, agents and grading. This serializes
processes on one host, not separate CI runners. No CI workflow is introduced.
Reset archives non-fixture context versions, parks extra tickets, replays the
manifest and compares full canonical content/version/links and ticket body/status.
A differing graph source gets one native archive/replay attempt. Orphan edges or
any remaining diff invalidate the run. Read-back is repeated immediately before
launch and after the cell; async inference drift must not be ignored. The project_jobs
gate drains before reset, after replay, before launch and after each cell, requiring
two ready observations five seconds apart (600-second bound). Delayed jobs count;
failed/dead-letter/unknown states, malformed replies and scope mismatches invalidate
the run. This gate requires STOMPY-2711 deployed and does not replace the full diff
or protect against external writers. Product
archive/history storage remains accessible: this is the explicitly requested
logical park/archive reset, not physical erasure or byte-identical DB restoration.

Each agent gets a fresh HOME and CLAUDE_CONFIG_DIR, a scrubbed environment and
only its run MCP configuration. Only the frozen source and fresh home are mounted;
no operator home, sockets, credentials or hidden tests. Nomemory gets no MCP
servers. Root and every identified child transcript are checked. A lead working alone
is a task-compliance failure (TASK_FAIL); a missing trace for an observed delegate
is INVALID. Unexpected MCP
servers, missing child traces, missing terminal results/costs, nonzero exits,
missing matrix cells and changed server SHAs fail closed. A memory cell must
actually call the scoped server. Agents receive read-only-fixture instructions;
post-cell comparison detects fixture writes but does not make the project key
itself read-only.

The task snapshot is `c40570b266df628ed1f5a9260ba77096d8bfe71a`. The fixture
contains historical context bodies and a completed historical ticket, all dated
before that commit, with provenance in `memory-fixture.json`; later answers and
dynamic recall neighbors are excluded. Context replay versions are explicit,
separate from source version provenance. No source Git history or operator
configuration goes into agent containers.

The grader runs eight fixed test identities in an immutable, networkless Docker
container outside the agent environment. Its submission mount is read-only;
hidden tests are mounted only into the grader. Three critical authorization
checks are separate from five points. These are transport/resolver contract
oracles using a controlled existing-MCP-tool seam, not a revalidation of the
existing lifecycle database implementation. The three critical checks patch private
resolver storage seams and are path-coupled; alternative correct authorization
implementations may not fit this oracle. Real MCP callable execution, agent-authored
both-door test quality, and optional review_after_days/note bounds are not scored.
RED on the untouched snapshot and
GREEN on the reference are retained in `results/spike-2699-preflight/`.

## Verification

```sh
python -m pytest tests/spike -q
python -m spike.red_proof
python -m spike.check_size
python -m spike.check_proxy_isolation
```

`red_proof` changes only behavior in disposable copies: credential leakage,
accepting a killed process and accepting an operator MCP connector each produce
exit **exactly 1**, the named regression failure, and surviving success controls.
The process-kill orchestration test really SIGKILLs a synthetic child and verifies
an INVALID/null-score row and nonzero orchestrator result. That is not evidence
that a paid Sonnet cell or its teammates completed. Separate live evidence in
results/spike-2699-live-controls proves the lead/teammate histogram axis and paid
SIGKILL handling: smoke-f made four accepted requests, CLI cost $0.28939515, gateway
upper bound $0.494433; the killed cell made one accepted request, gateway upper
bound $0.063720, terminal cost unknown. All comparison rows remain INVALID; these controls are not an n=2 result.

No skills are installed or changed. Skills impact: task agents now get isolated
configuration and an explicit scoped-memory instruction. The historical fixture
is task input, not a change to operator skills. New code is extracted into modules
below 500 lines; no existing file-size baseline is raised. Claude reviews/merges;
Markus alone decides tags. STOMPY-2704 staging two-door evidence is retained
in `results/spike-2699-live-controls/two-doors.json`. The project-key profile
route is intentionally forbidden; code-derived principal fields are labeled.

Live matrix attempt `matrix-20261010-a` was INVALID (1/4 rows): the original
1M cumulative-token cap rejected repeated cached history after 16 requests,
well before the $4.50 dollar ceiling. Its terminal cost was $0.61942995 and
gateway upper bound $1.377868; all evidence is retained. At that point the token ceiling was
derived from the cell dollar limit divided by the cheapest conservative
rate ($1/M), giving 4.5M tokens for a $4.50 cell. Worst-case dollar reservation,
unknown-billing refusal, and the shared $20 ledger remain enforced. This is
a versioned harness correction, not an automatic retry or discarded attempt.
`python -m spike.red_token_budget` restores the old limit and asserts the
named failing test at exit exactly 1 with the dollar-refusal control GREEN.

Final recorded spike answer: [report](../results/spike-2699-answer/report.md).
Both matrix attempts are INVALID at 1/4, with no nomemory score or paired delta.
Matrix-b also encountered the dollar reservation gate and staging build drift.
All-attempt gateway bounds are $6.115312; known terminal subtotal $2.65969785,
with killed-run terminal and service costs still unknown. The original remaining $13.884688 could not reserve another $18 matrix.
Markus subsequently approved the $25 cumulative ceiling below. Budget-refusal retries
and multiple invalidation reasons are tracked separately in STOMPY-2736.

## Split-rate follow-up (STOMPY-2699)

Reserve with a 1.5× safety factor using pinned Sonnet 4.6 standard/global
rates per million tokens: input $3, output $15, 5-minute cache write $3.75,
1-hour cache write $6, cache read $0.30. Settle confirmed response usage at
those rates, rounding up once per request to a microdollar. Missing write TTL
detail uses $6; malformed or missing usage retains the reservation and stops.
The token ceiling is now 15M for a $4.50 cell, derived from the cheapest rate.

Token counting does not reveal future cache hits. Only matching, unexpired,
usage-confirmed prefixes earn a cache-read forecast. A separate cold-cache
liability guard checks affordability at the $6 write rate with 1.5× safety
before sending. Thus a cache miss remains affordable, but a late request can
still be refused; this change does not guarantee a completed matrix. Audit
JSON records rates, safety, estimated split, reservation and cold liability.

The cell ceiling stays $4.50. The existing locked ledger gets a $25 cumulative
ceiling without deleting, refunding or repricing old attempts. Run once per
MAJOR release, not per tag. After Claude review/merge, coordinate the staging
window on STOMPY-2699 and announce the main-merge hold on the release-train
ticket before starting the approximately 90-minute matrix. SHA drift still
invalidates the run. No paid run is implied by this code change.

Run `python scripts/red/red_2699_split_rate.py` for named behavioral RED
proofs and surviving controls. Both Stompy doors: N/A for this gateway-only
slice; no MCP/REST/CLI surface or surface_contract changes. Skills impact:
no skill files change; gateway accounting/audit policy and operator budget
instructions change. STOMPY-2736 owns budget-refusal retries separately.

## Focused verification and failure reasons (STOMPY-2744 / 2736)

The harness appends the same focused verification guidance to both arms from
`spike/instructions.py`. It names existing lifecycle test modules at c40570b2
and asks for focused agent-authored REST/MCP tests. The pinned task prompt,
fixture and scorer are unchanged; harness and rendered-prompt hashes capture
the new instruction. No private grader test identities or answers are supplied.

Current benchmark-only envelope supersedes the $25 follow-up above: 1800-second
cell backstop, unchanged $4.50 cell ceiling, cumulative ledger $30. Preserve
all $9.216615 prior attempt bounds: $20.783385 remains, enough for one $18
matrix. This grants no retry budget. First Stompy cell runs first; any INVALID
halts the matrix before the remaining cells. No killed submission is graded.

Local budget refusal is HTTP402 / `invalid_request_error` with code
`local_budget_refusal`; its audited reason distinguishes `dollar budget exhausted`,
`token ceiling exceeded`, and unknown billing. Provider rate-limit responses
remain provider responses. Known usage over the token cap settles its known cost
and stops with the token reason; it is not labelled unknown billing.
Runner timeouts are `cell timeout (1800 s)` with wall_seconds. Independent
causes remain in `reasons` and in the generated report, including later build drift.

`python3 scripts/red/check_2736_cli.py` runs the pinned CLI against the real
gateway refusal in networkless containers: exactly one local request, exit1,
zero provider calls and no credential. `python3 scripts/red/red_2744.py` proves
named behavioral reverts with surviving controls. No CI workflow is added.

No paid run is part of this PR. Before a later reviewed matrix: wait for
STOMPY-2745 / backend PR1296 to land and staging to settle on its successor SHA;
verify the main merge queue EMPTY via the queue API, /check-logs clean on that
SHA (zero schema_not_on_connection in the shared-project walk), guardian quiet,
and announce the held window. Markus's strict gate excludes staging3c4f0f4d.
Skills impact: changed operator diagnostics and shared task verification guidance;
no skill files edited. Both Stompy doors N/A: no backend surface or resolver change.

## Design loop on a cheap local model (STOMPY-2800)

The verdict harness pins the Claude Code CLI, which only speaks the Anthropic
Messages API, so it cannot be driven by a local or non-Anthropic model. The
design loop is a separate, minimal runner for iterating on the benchmark's
own design (does the baseline saturate, does any check require recalled
state, is orientation cost measurable) at zero provider cost.

```sh
python -m spike.design_run --gen unique-name --condition nomemory --backend /path/to/dementia-production --grade
python -m spike.design_run --gen unique-name --condition stompy   --backend /path/to/dementia-production --grade
```

Same task artifact, fixture reset and read-back, snapshot, hidden-test grader
and prompt rendering as `spike.run`. Differences: the agent is an Ollama model
(default `gemma4:26b`, `--model`/`--ollama` to change) driven by
`spike/design_agent.py` with four tools (`bash`, `read_file`, `write_file`,
`done`) in a no-network hardened container; in the stompy arm five
`stompy_*` memory tools are executed on the host through `spike.mcp.MCP`
against the fixture project, so the container never holds the key. One cell
per invocation; `--no-fixture` skips the staging reset for the stompy arm.

Every row carries `mode: DESIGN`, `cost_usd: 0.0`, no ledger entry and a
limitation sentence. Design rows are never a verdict about Claude or Stompy
and are never compared with paid rows. The row adds the first handover
metrics (STOMPY-2801): `tokens`, `tool_histogram`, `memory_calls` and
`orientation` (turns, prompt tokens and seconds from launch up to and
including the first productive act: a `write_file`, or a `bash` command that
runs pytest). `orientation` is `null` when the agent never became productive.
