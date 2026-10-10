# STOMPY-2699 staging shadow spike

This is an incomplete release-gate spike, branched from `4ec5ffb` (PR #9).
The committed preflight report is **INCONCLUSIVE**. It is not a benchmark win,
production gate, or routed-tenant result. See STOMPY-2711: background entity
extraction recreated an inferred graph edge after an exact reset. The manifest
now explicitly includes that one edge from the retained c40570b2 preflight proof,
observed before any paid agent ran. Stable replay with readiness is still unproven.

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
ledger at `/private/tmp/stompy-2699-spend.json` caps all attempts together at $20;
unknown attempts keep their reservation. Never delete it to regain budget.
The planned smoke, kill and matrix ceilings total $19.50. Worker/embedding costs are
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
bound $0.063720, terminal cost unknown. All comparison rows remain INVALID pending
fixture stability; these controls are not an n=2 result.

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
gateway upper bound $1.377868; all evidence is retained. The token ceiling is
now derived from the cell dollar limit divided by the cheapest conservative
rate ($1/M), giving 4.5M tokens for a $4.50 cell. Worst-case dollar reservation,
unknown-billing refusal, and the shared $20 ledger remain enforced. This is
a versioned harness correction, not an automatic retry or discarded attempt.
`python -m spike.red_token_budget` restores the old limit and asserts the
named failing test at exit exactly 1 with the dollar-refusal control GREEN.
