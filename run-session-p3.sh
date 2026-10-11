#!/usr/bin/env bash
set -euo pipefail

# Usage: ./run-session-p3.sh MODEL CONDITION [--dry-run]
#
# Runs a single Phase 3 swarm benchmark session via Claude Code headless mode.
#
# Phase 3 differs from Phase 2:
#   - Multi-agent swarm (6 agents: 1 lead + 5 teammates)
#   - Single task (Duffel booking flow) instead of 3 independent tasks
#   - Higher budget/turns to accommodate team coordination
#   - dollar-flights codebase (Python/FastAPI + React/Vite)
#   - Two conditions: stompy (with Stompy MCP) and nomemory (no shared memory)
#
# MODEL:     Claude Code --model value (e.g., claude-opus-4-6)
# CONDITION: stompy, nomemory
#
# Environment:
#   DEMENTIA_API_KEY — required for stompy condition
#   MAX_TURNS_OVERRIDE — override max turns
#   MAX_BUDGET_OVERRIDE — override max budget USD
#   TIMEOUT_OVERRIDE    — override timeout in seconds

MODEL="${1:?Usage: $0 MODEL CONDITION [--dry-run]}"
CONDITION="${2:?Usage: $0 MODEL CONDITION [--dry-run]}"
DRY_RUN="${3:-}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
CONFIGS_DIR="$PROJECT_ROOT/configs"
PROMPTS_DIR="$PROJECT_ROOT/prompts/phase3"
SCORING_DIR="$PROJECT_ROOT/scoring/phase3"

# ─── Phase 3 parameters ─────────────────────────────────────────────

DEFAULT_TURNS=400
DEFAULT_BUDGET=35
DEFAULT_TIMEOUT=3900  # 65 min hard limit
SOFT_TIMEOUT_OFFSET=300  # 5 min grace before hard kill
TASK_NAME="duffel_booking_flow"

MAX_TURNS="${MAX_TURNS_OVERRIDE:-$DEFAULT_TURNS}"
MAX_BUDGET="${MAX_BUDGET_OVERRIDE:-$DEFAULT_BUDGET}"
TIMEOUT="${TIMEOUT_OVERRIDE:-$DEFAULT_TIMEOUT}"

RUN_DIR="$PROJECT_ROOT/runs/p3-${MODEL}-${CONDITION}"
RESULTS_DIR="$RUN_DIR"

# ─── Validate inputs ───────────────────────────────────────────────

case "$CONDITION" in
  stompy|nomemory) ;;
  *)
    echo "Error: CONDITION must be stompy or nomemory"
    exit 1
    ;;
esac

if [[ "$CONDITION" == stompy ]] && [ -z "${DEMENTIA_API_KEY:-}" ]; then
  echo "Error: DEMENTIA_API_KEY required for stompy condition"
  echo "  source ~/Sites/stompy/dementia-production/.env"
  exit 1
fi

# ─── Select prompt file ────────────────────────────────────────────

PROMPT_FILE="$PROMPTS_DIR/lead-${CONDITION}.md"

if [ ! -f "$PROMPT_FILE" ]; then
  echo "Error: Prompt file not found: $PROMPT_FILE"
  exit 1
fi

# ─── Banner ────────────────────────────────────────────────────────

echo "═══════════════════════════════════════════════════════════════════"
echo "  STOMPY BENCHMARK — Phase 3 Swarm Session Runner"
echo "═══════════════════════════════════════════════════════════════════"
echo "  Model:     $MODEL"
echo "  Condition: $CONDITION"
echo "  Task:      $TASK_NAME (6-agent swarm)"
echo "  Prompt:    $PROMPT_FILE"
echo "  Max turns: $MAX_TURNS"
echo "  Budget:    \$$MAX_BUDGET"
echo "  Timeout:   $(( (TIMEOUT - SOFT_TIMEOUT_OFFSET) / 60 ))m soft / $(( TIMEOUT / 60 ))m hard"
echo "═══════════════════════════════════════════════════════════════════"

# ─── Prepare run directory (fresh snapshot) ──────────────────────────

bash "$CONFIGS_DIR/phase3/clone-for-swarm.sh" "$MODEL" "$CONDITION"

# ─── MCP isolation ───────────────────────────────────────────────
# The run must see ONLY the MCP servers its condition declares. Without
# --strict-mcp-config the headless agent also loads the operator's user-level
# servers (107 tools across ~12 servers on the operator's machine), so a
# "stompy" run could use the operator's identity and a "nomemory" run could
# reach Stompy anyway. gen1 and gen2 both ran that way (results/gen2/summary.md).
if [[ "$CONDITION" == stompy ]]; then
  MCP_CONFIG_FILE="$RUN_DIR/.mcp.json"
else
  MCP_CONFIG_FILE="$RUN_DIR/.mcp-none.json"
  echo '{"mcpServers":{}}' > "$MCP_CONFIG_FILE"
fi
MCP_ARGS=(--strict-mcp-config --mcp-config "$MCP_CONFIG_FILE")

# ─── Dry run check ────────────────────────────────────────────────

if [ "$DRY_RUN" = "--dry-run" ]; then
  echo ""
  echo "[DRY RUN] Would execute:"
  echo "  cd $RUN_DIR"
  echo "  claude -p \"\$(cat $PROMPT_FILE)\" \\"
  echo "    --model $MODEL \\"
  echo "    --output-format stream-json \\"
  echo "    --verbose \\"
  echo "    --max-turns $MAX_TURNS \\"
  echo "    --max-budget-usd $MAX_BUDGET \\"
  echo "    --no-session-persistence \\"
  echo "    --strict-mcp-config --mcp-config $MCP_CONFIG_FILE \\"
  echo "    --permission-mode bypassPermissions"
  echo ""
  echo "  Output → $RESULTS_DIR/result.json"
  echo "  Scores → $RESULTS_DIR/scores.json"
  echo ""
  echo "Neutrality checks:"
  echo "  ✓ --no-session-persistence prevents session bleed"
  echo "  ✓ --max-turns=$MAX_TURNS, --max-budget-usd=$MAX_BUDGET"
  echo "  ✓ Fresh snapshot copy for this run"
  [[ "$CONDITION" == stompy ]] && echo "  ✓ .mcp.json present for Stompy MCP access"
  [[ "$CONDITION" != stompy ]] && echo "  ✓ No .mcp.json — Stompy MCP NOT available"
  echo "  ✓ No .git directory in run dir"
  echo "  ✓ No .env files in run dir"
  exit 0
fi

# ─── Run swarm session ───────────────────────────────────────────────

# Unset CLAUDECODE to allow nested headless invocations
unset CLAUDECODE 2>/dev/null || true

echo ""
echo "▶ Running Phase 3 swarm ($TASK_NAME)..."
START_TIME=$(date +%s)

PROMPT_CONTENT=$(cat "$PROMPT_FILE")
RESULT_FILE="$RESULTS_DIR/result.json"
RESULT_FILE_RAW="$RESULTS_DIR/result-stream.ndjson"

# Run Claude Code headless — the lead agent will spawn teammates
# Use stream-json (NDJSON) so output survives timeout kills (flushed line-by-line)
# Use SIGINT first (graceful shutdown), then SIGKILL after grace period
SOFT_TIMEOUT=$((TIMEOUT - SOFT_TIMEOUT_OFFSET))
cd "$RUN_DIR"
timeout --kill-after="$SOFT_TIMEOUT_OFFSET" -s INT "$SOFT_TIMEOUT" claude -p "$PROMPT_CONTENT" \
  --model "$MODEL" \
  --output-format stream-json \
  --verbose \
  --max-turns "$MAX_TURNS" \
  --max-budget-usd "$MAX_BUDGET" \
  --no-session-persistence \
  "${MCP_ARGS[@]}" \
  --permission-mode bypassPermissions \
  > "$RESULT_FILE_RAW" 2>"$RESULTS_DIR/stderr.log" || {
    EXIT_CODE=$?
    echo "⚠ Claude Code exited with code $EXIT_CODE"
    # Still continue to scoring — partial results are valuable
  }

END_TIME=$(date +%s)
WALL_CLOCK=$((END_TIME - START_TIME))

echo "  Duration: ${WALL_CLOCK}s ($(( WALL_CLOCK / 60 ))m $(( WALL_CLOCK % 60 ))s)"
echo "  Raw NDJSON: $RESULT_FILE_RAW ($(wc -l < "$RESULT_FILE_RAW" 2>/dev/null || echo 0) lines)"

# Extract final result from NDJSON stream
_NDJSON_RAW="$RESULT_FILE_RAW" _NDJSON_OUT="$RESULT_FILE" python3 << 'PYEOF'
import json, os

raw_file = os.environ["_NDJSON_RAW"]
out_file = os.environ["_NDJSON_OUT"]

last_result = None
with open(raw_file) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if obj.get("type") == "result":
                last_result = obj
        except (json.JSONDecodeError, ValueError):
            pass

if last_result:
    with open(out_file, "w") as f:
        json.dump(last_result, f, indent=2)
    print(f"  Extracted result object to {out_file}")
else:
    # Write empty object so downstream scoring doesn't break
    with open(out_file, "w") as f:
        json.dump({}, f)
    print(f"  ⚠ No result object found in NDJSON stream — wrote empty object to {out_file}")
PYEOF

echo "  Output:   $RESULT_FILE"

# A run whose MCP servers were not exactly its condition's is INVALID: the
# comparison it feeds is confounded. Record the verdict beside the result and
# stop before scoring so it cannot be aggregated by accident.
python3 "$PROJECT_ROOT/runners/check-isolation.py" "$CONDITION" "$RESULT_FILE_RAW" \
  --write "$RESULTS_DIR/isolation.json" || {
    echo "✗ RUN INVALID: MCP isolation check failed (see $RESULTS_DIR/isolation.json)"
    exit 3
  }

# Inject wall_clock_seconds and phase metadata into the result
if [ -f "$RESULT_FILE" ] && command -v python3 &>/dev/null; then
  python3 -c "
import json, sys
try:
    with open('$RESULT_FILE', 'r') as f:
        data = json.load(f)
    data['benchmark_wall_clock_seconds'] = $WALL_CLOCK
    data['benchmark_phase'] = 3
    data['benchmark_task_name'] = '$TASK_NAME'
    data['benchmark_condition'] = '$CONDITION'
    data['benchmark_model'] = '$MODEL'
    data['benchmark_agents'] = 6
    with open('$RESULT_FILE', 'w') as f:
        json.dump(data, f, indent=2)
except:
    pass  # Don't fail if result isn't valid JSON
"
fi

# ─── Scoring ────────────────────────────────────────────────────────

echo ""
echo "▶ Running scoring..."

SCORES_FILE="$RESULTS_DIR/scores.json"
SCORE_SCRIPT="$SCORING_DIR/score-booking.sh"

if [ ! -f "$SCORE_SCRIPT" ]; then
  echo "Error: Scoring script not found: $SCORE_SCRIPT"
  exit 1
fi

TASK_SCORE=$("$SCORE_SCRIPT" "$RUN_DIR" 2>/dev/null || echo '{"score":0,"max":40,"checks":[]}')

# Wrap score with metadata
python3 -c "
import json
task_score = json.loads('''$TASK_SCORE''')

result = {
    'model': '$MODEL',
    'condition': '$CONDITION',
    'phase': 3,
    'task_name': '$TASK_NAME',
    'agents': 6,
    'wall_clock_seconds': $WALL_CLOCK,
    'total_score': task_score['score'],
    'total_max': task_score['max'],
    'score_pct': round(task_score['score'] / task_score['max'] * 100, 2) if task_score['max'] > 0 else 0,
    'points_per_minute': round(task_score['score'] / ($WALL_CLOCK / 60), 4) if $WALL_CLOCK > 0 else 0,
    'task_scoring': task_score,
}

print(json.dumps(result, indent=2))
" > "$SCORES_FILE"

echo "  Scores: $SCORES_FILE"

# ─── Summary ────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "  Phase 3 Swarm ($TASK_NAME) complete"
if [ -f "$SCORES_FILE" ]; then
  python3 -c "
import json
with open('$SCORES_FILE') as f:
    s = json.load(f)
print(f\"  Score:    {s['total_score']}/{s['total_max']} ({s['score_pct']}%)\")
print(f\"  Time:     ${WALL_CLOCK}s ($(( WALL_CLOCK / 60 ))m $(( WALL_CLOCK % 60 ))s)\")
print(f\"  Eff:      {s['points_per_minute']} pts/min\")
print(f\"  Agents:   6 (1 lead + 5 teammates)\")
"
fi
echo "═══════════════════════════════════════════════════════════════════"
