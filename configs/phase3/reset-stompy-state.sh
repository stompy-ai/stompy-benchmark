#!/usr/bin/env bash
set -euo pipefail

# Usage: ./configs/phase3/reset-stompy-state.sh [--apply] [--project NAME]
#
# Restore the Phase 3 stompy fixture project to its canonical state before a
# re-run, so the `stompy` condition starts from the SAME memory as the original
# runs.
#
# WHY THIS EXISTS
#   The stompy condition runs against a shared, live Stompy project. Every run
#   leaves residue: the lead's `booking_api_contract` architecture lock (the
#   answer to the task!), teammate decisions, and tickets. `always_check`
#   contexts are pushed to the agent unasked, so a re-run against a dirty
#   project measures a polluted scenario — not "did Stompy improve?".
#
# WHAT IT KEEPS
#   configs/phase3/canonical-contexts.txt  — topics kept as-is
#   configs/phase3/canonical-tickets.txt   — ticket ids kept as-is
#
# WHAT IT REMOVES (reversibly)
#   Contexts not in the allowlist are ARCHIVED (stompy context unlock archives
#   by default) and exported to a timestamped manifest first, so nothing is
#   lost. Tickets not in the allowlist are moved to `parked`. Reverse with
#   `stompy context lock` from the manifest and `stompy ticket move <id>
#   --status backlog`.
#
# SAFETY
#   Default is a DRY RUN. Nothing changes without --apply.
#   Requirements: the `stompy` CLI, authenticated (`stompy whoami`).

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
CANONICAL_CONTEXTS="$SCRIPT_DIR/canonical-contexts.txt"
CANONICAL_TICKETS="$SCRIPT_DIR/canonical-tickets.txt"

PROJECT="dollar_flights"
APPLY=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply)   APPLY=true; shift ;;
    --project) PROJECT="$2"; shift 2 ;;
    -h|--help) sed -n '2,40p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

command -v stompy  >/dev/null || { echo "Error: stompy CLI not found in PATH"; exit 1; }
command -v python3 >/dev/null || { echo "Error: python3 required"; exit 1; }
[ -f "$CANONICAL_CONTEXTS" ] || { echo "Error: missing $CANONICAL_CONTEXTS"; exit 1; }
[ -f "$CANONICAL_TICKETS" ]  || { echo "Error: missing $CANONICAL_TICKETS"; exit 1; }

# Strip comments/blank lines into temp allowlists (grep -x membership below).
CANON_CTX_FILE=$(mktemp)
CANON_TIX_FILE=$(mktemp)
trap 'rm -f "$CANON_CTX_FILE" "$CANON_TIX_FILE"' EXIT
grep -vE '^[[:space:]]*(#|$)' "$CANONICAL_CONTEXTS" | sed -E 's/[[:space:]]+#.*$//; s/[[:space:]]+$//' > "$CANON_CTX_FILE"
grep -vE '^[[:space:]]*(#|$)' "$CANONICAL_TICKETS"  | sed -E 's/[[:space:]]+#.*$//; s/[[:space:]]+$//' > "$CANON_TIX_FILE"

MANIFEST_DIR="$PROJECT_ROOT/backups/reset-$(date +%Y%m%d-%H%M%S)"

echo "═══════════════════════════════════════════════════════════════════"
echo "  Phase 3 stompy fixture reset — project: $PROJECT"
echo "  Mode: $([ "$APPLY" = true ] && echo APPLY || echo 'DRY RUN (pass --apply to execute)')"
echo "  Canonical contexts: $(wc -l < "$CANON_CTX_FILE" | tr -d ' ')  tickets: $(wc -l < "$CANON_TIX_FILE" | tr -d ' ')"
echo "═══════════════════════════════════════════════════════════════════"

# ─── Contexts ────────────────────────────────────────────────────────

echo ""
echo "── Contexts ───────────────────────────────────────────────────────"

TOPICS=$(stompy context list -p "$PROJECT" -o json | python3 -c "
import json, sys
seen = set()
for row in json.load(sys.stdin):
    topic = (row.get('TOPIC') or '').strip()
    if topic:
        seen.add(topic)
print('\n'.join(sorted(seen)))
")

CTX_DRIFT=0
while IFS= read -r topic; do
  [ -z "$topic" ] && continue
  if grep -qxF "$topic" "$CANON_CTX_FILE"; then
    echo "  keep          $topic"
  else
    CTX_DRIFT=$((CTX_DRIFT + 1))
    if [ "$APPLY" = true ]; then
      mkdir -p "$MANIFEST_DIR"
      stompy context recall "$topic" -p "$PROJECT" -o json > "$MANIFEST_DIR/context--${topic}.json" 2>/dev/null || true
      stompy context unlock "$topic" -p "$PROJECT" --force --version all >/dev/null
      echo "  ARCHIVED      $topic  (export: $MANIFEST_DIR/context--${topic}.json)"
    else
      echo "  WOULD ARCHIVE $topic"
    fi
  fi
done <<< "$TOPICS"

# ─── Tickets ─────────────────────────────────────────────────────────

echo ""
echo "── Tickets ────────────────────────────────────────────────────────"

TICKETS=$(stompy ticket list -p "$PROJECT" -o json --limit 200 | python3 -c "
import json, sys
for row in json.load(sys.stdin):
    tid = str(row.get('ID') or '').strip()
    if tid:
        print(tid)
")

TIX_DRIFT=0
while IFS= read -r id; do
  [ -z "$id" ] && continue
  if grep -qxF "$id" "$CANON_TIX_FILE"; then
    echo "  keep       DF-$id"
  else
    TIX_DRIFT=$((TIX_DRIFT + 1))
    if [ "$APPLY" = true ]; then
      if stompy ticket move "$id" -p "$PROJECT" --status parked >/dev/null 2>&1; then
        echo "  PARKED     DF-$id"
      else
        echo "  !! could not park DF-$id (transition refused — handle manually)"
      fi
    else
      echo "  WOULD PARK DF-$id"
    fi
  fi
done <<< "$TICKETS"

# ─── Summary ─────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "  Residue found: $CTX_DRIFT context topic(s), $TIX_DRIFT ticket(s)"
if [ "$APPLY" = true ]; then
  echo "  Applied. Manifest: $MANIFEST_DIR"
  [ "$CTX_DRIFT" -gt 0 ] && [ -d "$MANIFEST_DIR" ] && echo "  Restore a context: stompy context lock --content @<manifest-file> -p $PROJECT"
  echo "  Next: ./configs/phase3/preload-stompy-contexts.sh  (idempotent; verifies canonical state)"
else
  echo "  Dry run — no changes made. Re-run with --apply to reset."
fi
echo "═══════════════════════════════════════════════════════════════════"
