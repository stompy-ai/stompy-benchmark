# gen2 vs gen1 — Phase 3 swarm benchmark (2026-10-09)

Same fixture (`dollar_flights` on prod), prompts, models and scoring; one sample per cell.
Tokens/turns are cumulative (normalizer fixed to use `modelUsage` and sum `num_turns`;
it reproduces the gen1 Opus figures exactly). gen1 re-derived from `backups/2026-10-09-pre-rerun/`.

| Model | Condition | gen1 | gen2 |
|-------|-----------|------|------|
| Opus 4.6 | stompy | 40/40 $4.34 29t 2.45M | 38/40 $5.95 50t 4.11M |
| Opus 4.6 | nomemory | 40/40 $7.65 70t 5.69M | 40/40 $7.76 74t 6.96M |
| Sonnet 4.6 | stompy | 40/40 $3.98 40t 3.03M | 40/40 $3.33 32t 4.47M |
| Sonnet 4.6 | nomemory | 40/40 $7.04 56t 6.43M | 40/40 $4.11 68t 6.53M |
| Haiku 4.5 | stompy | 39/40 $4.95 45t 7.16M | 31/40 $1.55 24t 7.49M |
| Haiku 4.5 | nomemory | 0/40 $3.97 53t 6.97M | 40/40 $2.33 52t 11.79M |

Memory cost saving (stompy vs nomemory): Opus 43% -> 23%, Sonnet 43% -> 19%.

## Caveats
- n=1 per cell. Haiku nomemory 0/40 -> 40/40 shows the variance is large (gen1 lead failed to
  delegate: 8 tool calls; gen2 teammates wrote the code). Do not read single deltas as signal.
- gen1 baseline for Haiku "memory enables capability" does not reproduce.
- No nomemory run called any Stompy tool, but all runs had the operator's user-level MCP servers
  connected. stompy-condition agents used the user-level `claude_ai_Stompy` / `stompy-direct`
  connectors (operator identity), never the injected project-key server — in both generations.
- Haiku stompy lost 9 pts: frontend components, passenger form, confirmation page, validation, error state.
- Opus stompy lost 2 pts: booking confirmation page.
