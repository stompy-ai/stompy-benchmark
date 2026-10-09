#!/usr/bin/env bash
set -euo pipefail

# Usage: ./clone-for-swarm.sh MODEL CONDITION
#
# Prepares a fresh run directory for a Phase 3 swarm benchmark run.
# Each run gets an independent copy of dollar-flights-snapshot/.
#
# MODEL:     claude-opus-4-6 (Claude Code --model value)
# CONDITION: stompy, nomemory

MODEL="${1:?Usage: $0 MODEL CONDITION}"
CONDITION="${2:?Usage: $0 MODEL CONDITION}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
SNAPSHOT_DIR="$PROJECT_ROOT/dollar-flights-snapshot"
CONFIGS_DIR="$PROJECT_ROOT/configs"

RUN_DIR="$PROJECT_ROOT/runs/p3-${MODEL}-${CONDITION}"

# Validate inputs
case "$CONDITION" in
  stompy|nomemory) ;;
  *)
    echo "Error: CONDITION must be stompy or nomemory (got: $CONDITION)"
    exit 1
    ;;
esac

if [ ! -d "$SNAPSHOT_DIR" ]; then
  echo "Error: Snapshot directory not found: $SNAPSHOT_DIR"
  echo "  Run: ./configs/phase3/prepare-snapshot.sh"
  exit 1
fi

# ─── Fresh copy from snapshot ────────────────────────────────────────

echo "Phase 3: Creating fresh copy from dollar-flights-snapshot/"

# Preserve any previous run for this condition instead of destroying it.
# Run artifacts are measurements — never delete them silently. See
# configs/benchmark-protocol.md ("Artifacts are append-only").
if [ -d "$RUN_DIR" ]; then
  ARCHIVE_ROOT="$PROJECT_ROOT/runs/_archive"
  ARCHIVE_DIR="$ARCHIVE_ROOT/$(date +%Y%m%d-%H%M%S)-$(basename "$RUN_DIR")"
  mkdir -p "$ARCHIVE_ROOT"
  mv "$RUN_DIR" "$ARCHIVE_DIR"
  echo "  Archived previous run -> $ARCHIVE_DIR"
fi
mkdir -p "$RUN_DIR"

# Copy snapshot (excludes .git since it was already stripped)
rsync -a --exclude='__pycache__' --exclude='*.pyc' \
  "$SNAPSHOT_DIR/" "$RUN_DIR/"

# Ensure no .git directory (safety check)
rm -rf "$RUN_DIR/.git"

# Ensure no .env files (prevent secret leakage)
find "$RUN_DIR" -name '.env*' -delete 2>/dev/null || true

# Remove any .claude-memory.db files
find "$RUN_DIR" -name '.claude-memory*' -delete 2>/dev/null || true

# ─── Inject condition-specific files ─────────────────────────────────

# Claude Code config directory
CLAUDE_DIR="$RUN_DIR/.claude"
mkdir -p "$CLAUDE_DIR"

# Settings — use condition-specific settings
SETTINGS_SRC="$CONFIGS_DIR/phase3/${CONDITION}-condition/settings.json"
if [ ! -f "$SETTINGS_SRC" ]; then
  echo "Error: Settings not found at $SETTINGS_SRC"
  exit 1
fi
cp "$SETTINGS_SRC" "$CLAUDE_DIR/settings.local.json"

# Stompy condition: inject .mcp.json
if [ "$CONDITION" = "stompy" ]; then
  MCP_SRC="$CONFIGS_DIR/phase3/stompy-condition/.mcp.json"
  if [ ! -f "$MCP_SRC" ]; then
    echo "Error: .mcp.json not found at $MCP_SRC"
    exit 1
  fi
  cp "$MCP_SRC" "$RUN_DIR/.mcp.json"
else
  # Ensure no .mcp.json in non-stompy conditions
  rm -f "$RUN_DIR/.mcp.json"
fi

# ─── OpenCode config (for non-Anthropic runners) ──────────────────────

# If this model uses OpenCode, inject .opencode/config.json for MCP
if [ "$CONDITION" = "stompy" ]; then
  OPENCODE_DIR="$RUN_DIR/.opencode"
  mkdir -p "$OPENCODE_DIR"
  if [ -n "${DEMENTIA_API_KEY:-}" ]; then
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
fi

# ─── Summary ─────────────────────────────────────────────────────────

echo ""
echo "Run directory ready: $RUN_DIR"
echo "  Model:     $MODEL"
echo "  Condition: $CONDITION"
echo "  Config:    $CLAUDE_DIR/settings.local.json"
[[ "$CONDITION" == stompy* ]] && echo "  MCP:       $RUN_DIR/.mcp.json (Claude Code)"
[[ "$CONDITION" == stompy* ]] && echo "  MCP:       $RUN_DIR/.opencode/config.json (OpenCode)"
echo ""

# Neutrality verification
echo "Neutrality checks:"
[[ "$CONDITION" == stompy* ]] && echo "  ✓ MCP configs injected for Stompy access (both runners)"
[[ "$CONDITION" != stompy* ]] && echo "  ✓ No MCP configs — Stompy NOT available"
echo "  ✓ Fresh snapshot copy (no state from other runs)"
echo "  ✓ No .git directory (prevents history-based knowledge)"
echo "  ✓ No .env files (prevents secret leakage)"
echo "  ✓ No .claude-memory.db files"
echo ""
