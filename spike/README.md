# STOMPY-2699 staging shadow spike

This is an incomplete release-gate spike, branched from `4ec5ffb` (PR #9).
The committed preflight report is **INCONCLUSIVE**. It is not a benchmark win,
production gate, or routed-tenant result. See STOMPY-2711: background entity
extraction can recreate a non-manifest graph edge after an exact reset.

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
Also provide exactly one explicitly authorized provider credential:
`ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN`. The harness never reads a keychain
or copies the operator's Claude login/configuration.

```sh
python -m spike.run --gen unique-name --backend /path/to/dementia-production
python -m spike.run --gen unique-kill-control --backend /path/to/dementia-production --kill-control
```

Normal schedule: Sonnet `stompy/1, nomemory/1, nomemory/2, stompy/2`; maximum
$4.50 per cell, $18 reserved total, no automatic retries. The separate killed
control reserves $0.25 and kills after ten seconds. Worker/embedding costs are
not metered, and killed processes may lack a terminal billing total; reports
preserve unknown costs. Do not describe the reserved amount as actual spend.
Output generations are append-only under ignored `runs/spike/`.

The fixed local advisory lock covers reset, agents and grading. This serializes
processes on one host, not separate CI runners. No CI workflow is introduced.
Reset archives non-fixture context versions, parks extra tickets, replays the
manifest and compares full canonical content/version/links and ticket body/status.
A differing graph source gets one native archive/replay attempt. Orphan edges or
any remaining diff invalidate the run. Read-back is repeated immediately before
launch and after the cell; async inference drift must not be ignored. Product
archive/history storage remains accessible: this is the explicitly requested
logical park/archive reset, not physical erasure or byte-identical DB restoration.

Each agent gets a fresh HOME and CLAUDE_CONFIG_DIR, a scrubbed environment and
only its run MCP configuration. Only the frozen source and fresh home are mounted;
no operator home, sockets, credentials or hidden tests. Nomemory gets no MCP
servers. Root and every identified child transcript are checked. Unexpected MCP
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
existing lifecycle database implementation. RED on the untouched snapshot and
GREEN on the reference are retained in `results/spike-2699-preflight/`.

## Verification

```sh
python -m pytest tests/spike -q
python -m spike.red_proof
python -m spike.check_size
```

`red_proof` changes only behavior in disposable copies: credential leakage,
accepting a killed process and accepting an operator MCP connector each produce
exit **exactly 1**, the named regression failure, and surviving success controls.
The process-kill orchestration test really SIGKILLs a synthetic child and verifies
an INVALID/null-score row and nonzero orchestrator result. That is not evidence
that a paid Sonnet cell or its teammates completed; those live proofs remain open.

No skills are installed or changed. Skills impact: task agents now get isolated
configuration and an explicit scoped-memory instruction. The historical fixture
is task input, not a change to operator skills. New code is extracted into modules
below 500 lines; no existing file-size baseline is raised. Claude reviews/merges;
Markus alone decides tags. STOMPY-2704's fixed staging two-door walk awaits its
reviewed deployment, independently of this spike's MCP fixture path.
