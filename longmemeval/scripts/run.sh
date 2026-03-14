#!/usr/bin/env bash
set -euo pipefail

# LongMemEval evaluation using Stompy retrieval
# Uses longmemeval_s_cleaned.json (~115K tokens, ~40 sessions per question)
#
# Run from stompy-benchmark/longmemeval/:
#   bash scripts/run.sh              # full eval (500 questions)
#   bash scripts/run.sh --limit 10   # smoke test

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LONGMEMEVAL_DIR="$(dirname "${SCRIPT_DIR}")"
PROJECT_ROOT="$(dirname "${LONGMEMEVAL_DIR}")"

# Source env from locomo (shared API keys)
source "${PROJECT_ROOT}/locomo/scripts/env.sh"

DATA_FILE="${LONGMEMEVAL_DIR}/longmemeval_repo/data/longmemeval_s_cleaned.json"
REF_FILE="${DATA_FILE}"
OUT_DIR="${LONGMEMEVAL_DIR}/outputs"

mkdir -p "${OUT_DIR}"

echo "=== LongMemEval Evaluation: Stompy Retrieval Mode ==="
echo "Stompy API: ${STOMPY_API_URL}"
echo "Data: ${DATA_FILE}"
echo "Model: claude-sonnet (via Stompy retrieval)"
echo ""

# Parse optional --limit flag for smoke tests
LIMIT_FLAG=""
if [[ "${1:-}" == "--limit" && -n "${2:-}" ]]; then
    LIMIT_FLAG="--limit ${2}"
    echo "*** SMOKE TEST: limiting to ${2} questions ***"
    echo ""
fi

for TOP_K in 10 20; do
    echo "--- Running with top_k=${TOP_K} ---"
    python3 "${LONGMEMEVAL_DIR}/adapter.py" \
        --data-file "${DATA_FILE}" \
        --out-dir "${OUT_DIR}" \
        --model claude-sonnet \
        --top-k "${TOP_K}" \
        ${LIMIT_FLAG} \
        --verbose
    echo ""
done

echo "=== Stompy retrieval evaluation complete ==="
echo ""

# Run GPT-4o judge if OPENAI_API_KEY is set
if [[ -n "${OPENAI_API_KEY:-}" ]]; then
    echo "=== Running GPT-4o judge evaluation ==="
    EVAL_DIR="${LONGMEMEVAL_DIR}/longmemeval_repo/src/evaluation"
    for TOP_K in 10 20; do
        HYP_FILE="${OUT_DIR}/stompy_predictions_top${TOP_K}.jsonl"
        if [[ -f "${HYP_FILE}" ]]; then
            echo "--- Evaluating top_k=${TOP_K} ---"
            python3 "${EVAL_DIR}/evaluate_qa.py" gpt-4o "${HYP_FILE}" "${REF_FILE}"
            echo ""
            echo "--- Category breakdown ---"
            python3 "${EVAL_DIR}/print_qa_metrics.py" "${HYP_FILE}.eval-results-gpt-4o" "${REF_FILE}"
            echo ""
        fi
    done
    echo "=== GPT-4o judge evaluation complete ==="
else
    echo "Set OPENAI_API_KEY to run GPT-4o judge scoring."
    echo "Manual scoring:"
    echo "  cd longmemeval_repo/src/evaluation"
    echo "  python3 evaluate_qa.py gpt-4o ../../outputs/stompy_predictions_top10.jsonl ../../longmemeval_repo/data/longmemeval_s_cleaned.json"
fi

echo ""
echo "Results in ${OUT_DIR}/"
echo "Check *_retrieval_analysis_*.json for per-question retrieval details."
