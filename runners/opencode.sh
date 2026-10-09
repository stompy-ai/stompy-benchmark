#!/usr/bin/env bash
set -euo pipefail

# Usage: ./runners/opencode.sh MODEL CONDITION [--dry-run]
#
# OpenCode headless runner for the Stompy benchmark.
# Uses OpenCode CLI for non-Anthropic models (and optionally Anthropic too).
# OpenCode supports MCP natively — Stompy works without adaptation.
#
# MODEL:     Benchmark model ID from models.json (e.g., gpt-5.1-codex, gemini-2.5-pro)
#            Resolved to opencode_model format (e.g., openai/gpt-5.1-codex)
# CONDITION: stompy, nomemory
#
# OpenCode outputs NDJSON events (step_start, text, tool_call, step_finish).
# Token data is in step_finish events under part.tokens.
#
# Environment:
#   DEMENTIA_API_KEY   — required for stompy condition
#   TIMEOUT_SECONDS    — override timeout (default: 3900)
#   RUN_DIR            — override run directory path
#
# Prerequisites:
#   - OpenCode CLI installed: brew install opencode or go install
#   - Provider API key set (OPENAI_API_KEY, GOOGLE_API_KEY, etc.)
#   - Or opencode auth configured

MODEL="${1:?Usage: $0 MODEL CONDITION [--dry-run]}"
CONDITION="${2:?Usage: $0 MODEL CONDITION [--dry-run]}"
DRY_RUN="${3:-}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# ─── Resolve model config from registry ───────────────────────────────

MODEL_CONFIG=$(python3 -c "
import json, sys
with open('$PROJECT_ROOT/configs/models.json') as f:
    data = json.load(f)
for m in data['models']:
    if m['id'] == '$MODEL':
        print(json.dumps(m))
        sys.exit(0)
print('{}')
" 2>/dev/null || echo '{}')

# OpenCode uses provider/model format (e.g., openai/gpt-5.1-codex)
OPENCODE_MODEL=$(echo "$MODEL_CONFIG" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(d.get('opencode_model', d.get('id', '$MODEL')))
" 2>/dev/null || echo "$MODEL")

TIMEOUT="${TIMEOUT_SECONDS:-3900}"
SOFT_TIMEOUT_OFFSET=300

if [ -z "${RUN_DIR:-}" ]; then
  RUN_DIR="$PROJECT_ROOT/runs/p3-${MODEL}-${CONDITION}"
fi

PROMPTS_DIR="$PROJECT_ROOT/prompts/phase3"
PROMPT_FILE="$PROMPTS_DIR/lead-${CONDITION}.md"

# ─── Validate condition ───────────────────────────────────────────────

case "$CONDITION" in
  stompy|nomemory) ;;
  *)
    echo "Error: CONDITION must be stompy or nomemory (got: $CONDITION)"
    exit 1
    ;;
esac

# ─── Dry run (check early, before strict validation) ─────────────────

if [ "$DRY_RUN" = "--dry-run" ]; then
  echo "[DRY RUN] OpenCode runner"
  echo "  Model (benchmark): $MODEL"
  echo "  Model (opencode):  $OPENCODE_MODEL"
  echo "  Condition:         $CONDITION"
  echo "  Run dir:           $RUN_DIR"
  echo "  Timeout:           $(( (TIMEOUT - SOFT_TIMEOUT_OFFSET) / 60 ))m soft / $(( TIMEOUT / 60 ))m hard"
  echo "  Prompt:            $PROMPT_FILE"
  echo ""
  echo "  Command:"
  echo "    cd $RUN_DIR"
  echo "    opencode run \"\$(cat $PROMPT_FILE)\" \\"
  echo "      --model $OPENCODE_MODEL \\"
  echo "      --format json \\"
  echo "      --dir $RUN_DIR"
  [[ "$CONDITION" == stompy ]] && echo "  MCP: Stompy via .opencode/config.json"
  exit 0
fi

# ─── Strict validation (only for real runs) ───────────────────────────

if [[ "$CONDITION" == stompy ]] && [ -z "${DEMENTIA_API_KEY:-}" ]; then
  echo "Error: DEMENTIA_API_KEY required for stompy condition"
  exit 1
fi

if [ ! -f "$PROMPT_FILE" ]; then
  echo "Error: Prompt file not found: $PROMPT_FILE"
  exit 1
fi

if [ ! -d "$RUN_DIR" ]; then
  echo "Error: RUN_DIR does not exist: $RUN_DIR"
  exit 1
fi

if ! command -v opencode &>/dev/null; then
  echo "Error: opencode CLI not found"
  echo "  Install: brew install opencode"
  exit 1
fi

# ─── Prepare OpenCode MCP config ──────────────────────────────────────

if [ "$CONDITION" = "stompy" ]; then
  OPENCODE_DIR="$RUN_DIR/.opencode"
  mkdir -p "$OPENCODE_DIR"
  cat > "$OPENCODE_DIR/config.json" << OCEOF
{
  "mcpServers": {
    "stompy": {
      "type": "sse",
      "url": "${BENCH_STOMPY_URL:-https://api.stompy.ai}/mcp/sse",
      "headers": {
        "Authorization": "Bearer ${DEMENTIA_API_KEY}"
      }
    }
  }
}
OCEOF
fi

# ─── Run ──────────────────────────────────────────────────────────────

echo "▶ OpenCode runner: $MODEL ($OPENCODE_MODEL) / $CONDITION"
START_TIME=$(date +%s)

PROMPT_CONTENT=$(cat "$PROMPT_FILE")
RESULT_FILE_RAW="$RUN_DIR/result-stream.ndjson"
RESULT_FILE="$RUN_DIR/result.json"
STDERR_LOG="$RUN_DIR/stderr.log"

SOFT_TIMEOUT=$((TIMEOUT - SOFT_TIMEOUT_OFFSET))

# OpenCode headless invocation
# --format json outputs NDJSON events (step_start, text, tool_call, step_finish)
# --dir sets working directory without cd (preserves shell state)
timeout --kill-after="$SOFT_TIMEOUT_OFFSET" -s INT "$SOFT_TIMEOUT" opencode run "$PROMPT_CONTENT" \
  --model "$OPENCODE_MODEL" \
  --format json \
  --dir "$RUN_DIR" \
  > "$RESULT_FILE_RAW" 2>"$STDERR_LOG" || {
    EXIT_CODE=$?
    echo "  ⚠ OpenCode exited with code $EXIT_CODE"
  }

END_TIME=$(date +%s)
WALL_CLOCK=$((END_TIME - START_TIME))

echo "  Duration: ${WALL_CLOCK}s ($(( WALL_CLOCK / 60 ))m $(( WALL_CLOCK % 60 ))s)"
echo "  Raw NDJSON: $RESULT_FILE_RAW ($(wc -l < "$RESULT_FILE_RAW" 2>/dev/null || echo 0) lines)"

# ─── Extract result from NDJSON stream ────────────────────────────────
# OpenCode NDJSON events:
#   step_start  → {type, sessionID, part: {type: "step-start"}}
#   text        → {type, sessionID, part: {type: "text", text: "..."}}
#   tool_call   → {type, sessionID, part: {type: "tool-call", ...}}
#   tool_result → {type, sessionID, part: {type: "tool-result", ...}}
#   step_finish → {type, sessionID, part: {type: "step-finish", cost, tokens: {total, input, output, cache: {read, write}}}}

_NDJSON_RAW="$RESULT_FILE_RAW" _NDJSON_OUT="$RESULT_FILE" _WALL_CLOCK="$WALL_CLOCK" _MODEL="$MODEL" _CONDITION="$CONDITION" \
python3 << 'PYEOF'
import json, os

raw_file = os.environ["_NDJSON_RAW"]
out_file = os.environ["_NDJSON_OUT"]
wall_clock = int(os.environ["_WALL_CLOCK"])
model = os.environ["_MODEL"]
condition = os.environ["_CONDITION"]

total_input = 0
total_output = 0
total_cache_read = 0
total_cache_write = 0
total_cost = 0.0
session_id = ""
num_steps = 0
text_parts = []

with open(raw_file) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue

        if not session_id and obj.get("sessionID"):
            session_id = obj["sessionID"]

        event_type = obj.get("type", "")
        part = obj.get("part", {})

        if event_type == "step_finish":
            num_steps += 1
            tokens = part.get("tokens", {})
            total_input += tokens.get("input", 0)
            total_output += tokens.get("output", 0)
            cache = tokens.get("cache", {})
            total_cache_read += cache.get("read", 0)
            total_cache_write += cache.get("write", 0)
            total_cost += part.get("cost", 0)

        elif event_type == "text":
            text_parts.append(part.get("text", ""))

result = {
    "type": "result",
    "benchmark_runner": "opencode",
    "benchmark_model": model,
    "benchmark_condition": condition,
    "benchmark_phase": 3,
    "benchmark_wall_clock_seconds": wall_clock,
    "session_id": session_id,
    "num_turns": num_steps,
    "total_cost_usd": round(total_cost, 6),
    "is_error": False,
    "duration_ms": wall_clock * 1000,
    "duration_api_ms": 0,
    "usage": {
        "input_tokens": total_input,
        "output_tokens": total_output,
        "cache_read_input_tokens": total_cache_read,
        "cache_creation_input_tokens": total_cache_write,
    },
    "result": "".join(text_parts[-3:]) if text_parts else "",
}

with open(out_file, "w") as f:
    json.dump(result, f, indent=2)

total_tokens = total_input + total_output + total_cache_read + total_cache_write
print(f"  Extracted: {num_steps} steps, {total_tokens:,} tokens, ${total_cost:.4f}")
PYEOF

echo "  Result: $RESULT_FILE"
echo "  Wall clock: $WALL_CLOCK"
