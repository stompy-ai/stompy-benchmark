# Stompy Benchmark

**Measuring the impact of persistent AI memory on multi-agent coding performance.**

Stompy Benchmark is a controlled experimental framework that quantifies how persistent project memory (via [Stompy MCP](https://github.com/banton/dementia-production)) affects the cost, speed, and quality of AI-driven software engineering — from single-agent tasks to multi-agent swarms.

## The Question

> If an AI coding agent can recall architecture decisions, API patterns, and testing conventions from previous sessions, does it write better code faster and cheaper — or is re-exploring the codebase each time just as effective?

## Key Findings

### Phase 3: Multi-Agent Swarm (6 agents, Duffel booking feature)

| Metric | With Memory | Without Memory | Delta |
|--------|-------------|----------------|-------|
| Score | 40/40 (100%) | 40/40 (100%) | Tied |
| API Cost | **$2.34** | **$3.30** | **29% cheaper** |
| API Time | 6.2 min | 8.2 min | **33% faster** |
| Code Output | 2,103 lines | 2,718 lines | Memory is more concise |

Memory doesn't make agents *smarter* — it makes them *cheaper*. Recalled contexts eliminate codebase exploration overhead, reducing token consumption across the entire team.

### Phase 2: Single-Agent Tasks (3 tasks, dementia-production codebase)

| Condition | Avg Score | Avg Cost | Avg Time |
|-----------|-----------|----------|----------|
| Stompy MCP | 95% | $0.42 | 2.1 min |
| File-based memory | 88% | $0.51 | 2.8 min |
| No memory | 82% | $0.58 | 3.2 min |

### Phase 1: Session Continuity (Meridian Logistics API)

Validated that Stompy contexts survive across sessions and that agents recall architectural decisions without re-reading code.

## How It Works

### Experimental Design

Each benchmark run:

1. **Snapshots** a real codebase (no `.git`, no `.env`, no prior state)
2. **Assigns a task** via a condition-specific prompt
3. **Runs Claude Code** in headless mode with controlled parameters
4. **Scores the output** against a rubric of automated checks
5. **Captures cost, turns, and timing** from the NDJSON stream

### Conditions

| Condition | Memory Source | How Agent Gets Context |
|-----------|-------------|----------------------|
| `stompy` | Stompy MCP (PostgreSQL-backed) | `recall_context()` — instant structured recall |
| `file` | CLAUDE.md + memory files | Reads files from disk |
| `nomemory` | None | Explores codebase from scratch |

### Controls

- Same model, budget, turn limit, and timeout across conditions
- Fresh codebase snapshot per run (no cross-condition bleed)
- `--no-session-persistence` prevents session history leakage
- Deterministic scoring rubrics with binary pass/fail checks

## Repository Structure

```
stompy-benchmark/
├── prompts/                    # Task prompts per phase and condition
│   ├── phase2/                 #   Single-agent tasks (3 tasks x 3 conditions)
│   └── phase3/                 #   Multi-agent swarm (lead-stompy.md, lead-nomemory.md)
├── configs/                    # Run configurations
│   ├── phase3/                 #   Swarm setup: snapshot cloning, MCP injection
│   ├── stompy-condition/       #   .mcp.json for Stompy access
│   └── nomemory-condition/     #   Bare settings (no MCP)
├── scoring/                    # Automated scoring scripts
│   ├── phase2/                 #   score-task{1,2,3}.sh
│   └── phase3/                 #   score-booking.sh (24 checks, 40 points)
├── analysis/                   # TypeScript analysis tools
├── reports/                    # Written analysis
│   └── phase3-analysis.md      #   Full Phase 3 report
├── results/                    # Aggregated result data
├── runs/                       # Run artifacts (gitignored)
├── run-session.sh              # Phase 1 runner
├── run-session-p2.sh           # Phase 2 runner
├── run-session-p3.sh           # Phase 3 runner (stream-json + NDJSON extraction)
├── dementia-snapshot/          # Phase 2 codebase snapshot
└── dollar-flights-snapshot/    # Phase 3 codebase snapshot
```

## Running a Benchmark

### Prerequisites

- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed
- Anthropic API key configured
- For `stompy` condition: running Stompy MCP server + `DEMENTIA_API_KEY`

### Phase 3 (Multi-Agent Swarm)

```bash
# Dry run — verify configuration without spending tokens
./run-session-p3.sh claude-opus-4-6 stompy --dry-run
./run-session-p3.sh claude-opus-4-6 nomemory --dry-run

# Real run (~60 min, ~$3-5 per condition)
export DEMENTIA_API_KEY=your-key-here
./run-session-p3.sh claude-opus-4-6 stompy
./run-session-p3.sh claude-opus-4-6 nomemory
```

> **Re-running for comparison?** Read [`configs/benchmark-protocol.md`](configs/benchmark-protocol.md)
> first. The `stompy` condition writes to a live shared Stompy project, so a
> stale run's architecture lock can leak into the next measurement. Reset the
> fixture with `./configs/phase3/reset-stompy-state.sh --apply` before the
> `stompy` run, and archive old runs before re-running. Old results are never
> deleted: `clone-for-swarm.sh` moves prior run dirs to `runs/_archive/`.

### Phase 2 (Single-Agent Tasks)

```bash
# Run all 3 tasks x 3 conditions
./run-all-p2.sh claude-opus-4-6
```

### Output

Each run produces:
- `result-stream.ndjson` — Full NDJSON event stream (survives timeouts)
- `result.json` — Extracted final result with cost/turns/timing
- `scores.json` — Automated scoring breakdown
- `stderr.log` — Runtime errors

## Benchmark Phases

| Phase | Scope | Agents | Codebase | Task |
|-------|-------|--------|----------|------|
| 1 | Session continuity | 1 | Meridian Logistics (Express/TS) | Build API across 3 sessions |
| 2 | Single-agent tasks | 1 | dementia-production (Python/FastAPI) | 3 independent tasks |
| 3 | Multi-agent swarm | 6 | dollar-flights (Python/FastAPI + React) | Complete booking feature |

## Instrumentation Lessons

Learned through three iterations of Phase 3:

1. **`--output-format json` loses data on timeout** — it buffers everything and flushes on exit. Use `stream-json --verbose` for NDJSON that survives `SIGINT`/`SIGKILL`.

2. **Multi-agent path isolation is critical** — teammates inherit the lead's CWD. If any context contains absolute paths, teammates write to the wrong directory. Enforce relative paths in prompts.

3. **Codebase snapshots must be stateless** — remove `.git` (prevents history-based knowledge), `.env` (prevents secret leakage), and any memory databases.

## Future Work

- **Harder scoring rubrics** — runtime test execution, import resolution, style consistency scoring
- **More models** — compare across Claude Sonnet, GPT-4o, Gemini Pro
- **Larger codebases** — test whether memory savings scale with codebase size
- **Cost-at-parity analysis** — find the score threshold where memory becomes necessary, not just efficient
- **Open-source the framework** — generalize beyond Stompy to any MCP-based memory provider

## License

MIT — see [LICENSE](LICENSE).
