# Benchmark Protocol — a repeatable measurement model

This is the runbook for producing a **comparable** set of Stompy benchmark
numbers. It exists because two problems were found when trying to re-run
Phase 3 after improving Stompy:

1. **Artifacts were destroyed.** `configs/phase3/clone-for-swarm.sh` did
   `rm -rf runs/p3-<model>-<condition>` on every run. `runs/` is gitignored, so
   re-running the same model+condition silently deleted the previous
   `result.json`, `scores.json`, `result-stream.ndjson`, and the agent's code.
2. **The stompy fixture was polluted.** The `stompy` condition runs against a
   *live, shared* Stompy project (`dollar_flights`). Every run left residue —
   most importantly the lead's `booking_api_contract` architecture lock (i.e.
   the answer to the task) plus 18 tickets. Because that lock is `always_check`,
   a re-run began with the solution already in memory. That is not a
   re-measurement of "did Stompy improve?"; it is a different experiment.

A result is only meaningful if the *only* thing that changed between the old
and new numbers is the thing you improved. Everything below protects that.

---

## 1. Generations

Every measurement belongs to a **generation (`gen`)** — a frozen tuple of
(Stompy version, fixture snapshot, prompts, models, harness). Numbers are only
compared *within* and *across* generations, never mixed opportunistically.

| Generation | What it measures | Status |
|-----------|------------------|--------|
| `gen1` | Original Phase 3 baseline (README / `configs/run-matrix.md`) | recorded |
| `gen2` | Stompy after the recent improvements, same fixture + prompts | to run |

To claim "Stompy improved", re-run the **same matrix in both conditions** under
`gen2` and compare `gen2` against `gen1`. Never compare a fresh `stompy` run
against an old `nomemory` run.

## 2. Canonical fixture state

The `dollar_flights` project must contain exactly the topics in
`configs/phase3/canonical-contexts.txt` and the tickets in
`configs/phase3/canonical-tickets.txt` before any `stompy` run.

- The five `dollar_flights_*` topics are the preloaded fixture.
- Four legacy topics predate the benchmark and were present during `gen1`, so
  they stay (removing them would itself change the scenario).
- Everything else — `booking_api_contract`, `duffel_booking_architecture`, the
  benchmark-created tickets — is residue and is removed before a run.

Reset (dry-run by default):

```bash
./configs/phase3/reset-stompy-state.sh            # show what would change
./configs/phase3/reset-stompy-state.sh --apply    # archive residue + park tickets
./configs/phase3/preload-stompy-contexts.sh       # re-assert the 5 preloaded topics
```

`reset-stompy-state.sh` **archives** contexts (recoverable) and exports each to
a timestamped manifest under `backups/reset-*/` before removing it.

## 3. Artifacts are append-only

- `clone-for-swarm.sh` now moves any prior run dir to
  `runs/_archive/<timestamp>-<name>/` instead of deleting it.
- Before a re-run, snapshot the current evidence:
  `mkdir -p backups/$(date +%F)-pre-rerun && cp -a runs results backups/$(date +%F)-pre-rerun/`
- `backups/` is gitignored. Tracked aggregates (`results/phase*-results.json`)
  are the durable summary; `runs/` is the raw evidence.

## 4. Controlled variables (must be identical across conditions)

| Control | Where |
|---------|-------|
| Prompt | `prompts/phase3/lead-{stompy,nomemory}.md` (change = new gen) |
| Codebase | `dollar-flights-snapshot/` (stateless: no `.git`, `.env`, `*.db`) |
| Budget / turns / timeout | `configs/models.json` → `runners/*.sh` |
| Model + runner | `configs/models.json` |
| Scoring | `scoring/phase3/score-booking.sh` (40 pts, 24 checks) |

`--no-session-persistence` and `--permission-mode bypassPermissions` are fixed
in the runner. Do not tune one condition.

## 5. Measurement model

For each model, run **both** conditions and record per run:

| Metric | Source |
|--------|--------|
| `score` / `max_score` | `scores.json` |
| `cost_usd` | `result.json` (`total_cost_usd`) |
| `tokens.total` (in + out + cache) | `result.json` usage |
| `turns` | `result.json` |
| `wall_clock_seconds` | runner timer |
| `points_per_minute`, `cost_per_point` | `runners/normalize-result.py` |

Primary claim is the **paired delta** for a model: `stompy − nomemory` on cost,
tokens, time, and score. Report score deltas separately from cost deltas —
memory has repeatedly *not* changed score for capable models while cutting cost.

## 6. Recommended `gen2` matrix

Re-run the three Anthropic leads first (cheap, directly comparable to `gen1`),
then extend cross-provider. Add models only if they are run in **both**
conditions.

| # | Model | Runner | Why |
|---|-------|--------|-----|
| 1 | claude-opus-4-6 | claude-code | Frontier baseline; `gen1` had 70 vs 29 turns |
| 2 | claude-sonnet-4-6 | claude-code | Best value in `gen1` ($3.98) |
| 3 | claude-haiku-4-5 | claude-code | Capability test: 0/40 → 39/40 in `gen1` |
| 4 | gpt-5.1-codex | opencode | Cross-provider control (deferred from `gen1`) |
| 5 | gemini-2.5-pro | opencode | Cross-provider control (deferred from `gen1`) |

Run order per model: `reset` → `stompy` → `clone` (archive) → `nomemory`.
Optionally add a second `stompy` run to estimate variance before drawing strong
conclusions from a single sample.

## 7. Pre-run checklist

```text
[ ] backup/archive current runs + results
[ ] ./configs/phase3/reset-stompy-state.sh            # inspect
[ ] ./configs/phase3/reset-stompy-state.sh --apply    # reset fixture
[ ] ./configs/phase3/preload-stompy-contexts.sh       # verify canonical topics
[ ] stompy ticket board -p dollar_flights              # confirm only canonical tickets
[ ] for each model: run stompy AND nomemory under the same gen
[ ] confirm no run dir was clobbered (runs/_archive/ grows, not shrinks)
[ ] aggregate + record gen in results/
```

## 8. Future work (harness)

- **Versioned run paths** — `runs/<gen>/p3-<model>-<condition>` so generations
  never share names (the archive step is a safety net, not the design).
- **Disposable fixture project** — template the prompt's
  `project="dollar_flights"` from an env var and run against a per-gen project
  (e.g. `dollar_flights_gen2`) that is created and torn down, eliminating
  residue by construction instead of by cleanup.
- **Runtime scoring** — execute the produced tests, not just presence checks.
- **Variance runs** — n≥3 per cell for confidence intervals.
