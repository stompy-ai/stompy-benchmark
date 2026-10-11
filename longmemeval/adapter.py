"""
LongMemEval → Stompy adapter for benchmark evaluation.

Adapts LongMemEval (ICLR 2025) dataset format to Stompy's REST API,
following the same patterns as stompy_utils.py for LOCOMO.

LongMemEval tests 5 memory abilities:
  IE  — Information Extraction (single-session-user, single-session-assistant, single-session-preference)
  MR  — Multi-Session Reasoning (multi-session)
  TR  — Temporal Reasoning (temporal-reasoning)
  KU  — Knowledge Updates (knowledge-update)
  ABS — Abstention (questions with _abs suffix)

Pipeline:
  1. Load LongMemEval JSON (500 questions with timestamped haystack sessions)
  2. For each question: load haystack sessions as Stompy contexts
  3. Search Stompy for relevant sessions → retrieve context
  4. Call Claude with retrieved context → generate answer
  5. Output JSONL (question_id, hypothesis) for LongMemEval's GPT-4o judge
"""

import sys
from pathlib import Path

# Add LOCOMO's task_eval to path for shared StompyClient and helpers
_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "locomo" / "task_eval"))

import os
import json
import logging
import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Optional

from tqdm import tqdm

# Reuse StompyClient and helpers from the LOCOMO adapter
from stompy_utils import (
    StompyClient,
    make_project_name,
    run_llm,
    strip_markdown,
    extract_short_answer,
    extract_final_answer,
    expand_query,
    decompose_query,
    merge_multi_query_results,
    rerank_results,
    PER_QA_TOKEN_BUDGET,
    COT_TOKEN_BUDGET,
)

logger = logging.getLogger("longmemeval.stompy")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

QUESTION_TYPE_TO_CATEGORY = {
    "single-session-user": "IE",
    "single-session-assistant": "IE",
    "single-session-preference": "IE",
    "multi-session": "MR",
    "temporal-reasoning": "TR",
    "knowledge-update": "KU",
}

# Override token budgets — LongMemEval answers are longer than LOCOMO's terse facts
LONGMEMEVAL_TOKEN_BUDGET = 150
LONGMEMEVAL_COT_TOKEN_BUDGET = 300

# Numeric category codes for compatibility with stompy_utils expand_query/decompose_query
CATEGORY_TO_NUMERIC = {
    "IE": 4,   # single-hop equivalent
    "MR": 1,   # multi-hop equivalent
    "TR": 2,   # temporal equivalent
    "KU": 4,   # single-hop equivalent (tracking latest state)
    "ABS": 5,  # adversarial equivalent
}


# ---------------------------------------------------------------------------
# Prompts — adapted from LongMemEval's own reader prompts
# ---------------------------------------------------------------------------

QA_PROMPT = """You are a helpful assistant with access to the user's conversation history. Based on the conversations above, answer the following question with ONLY a short phrase or name. Do NOT explain or hedge. Just the answer.

Question: {question}
Answer:"""

QA_PROMPT_TEMPORAL = """You are a helpful assistant with access to the user's conversation history. Based on the conversations above, answer the following question about timing or dates. Pay attention to the DATE headers of each session. Give ONLY the date or time period — no explanation.

Question: {question}
Answer:"""

QA_PROMPT_KNOWLEDGE_UPDATE = """You are a helpful assistant with access to the user's conversation history. Based on the conversations above, answer the following question. If the information changed over time, give the MOST RECENT answer. Give ONLY a short phrase — no explanation.

Question: {question}
Answer:"""

QA_PROMPT_ABSTENTION = """You are a helpful assistant with access to the user's conversation history. Based on the conversations above, answer the following question. If the required information was never discussed in any conversation, say "I don't know." Otherwise, give a concise answer.

Question: {question}
Answer:"""

QA_PROMPT_PREFERENCE = """You are a helpful assistant with access to the user's conversation history. Based on the conversations above, answer the following question about the user's preferences or personal information. Give ONLY a short phrase — no explanation.

Question: {question}
Answer:"""

COT_PROMPT = """Based on the retrieved conversation history above, answer the following question.

Think briefly (1-2 sentences) inside <thinking> tags about which conversation session(s) contain the answer. Then give ONLY the answer inside <final_answer> tags.

Question: {question}"""

COT_PROMPT_TEMPORAL = """Based on the retrieved conversation history above, answer the following question about timing or dates.

Think briefly (1-2 sentences) inside <thinking> tags: find the relevant session(s), note the DATE header(s), and compute the answer. Then give ONLY the answer inside <final_answer> tags.

Question: {question}"""


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------

def load_longmemeval_dataset(
    data_file: str,
    limit: Optional[int] = None,
) -> list[dict]:
    """Load LongMemEval JSON dataset.

    Args:
        data_file: Path to longmemeval_s_cleaned.json or longmemeval_oracle.json
        limit: Optional limit on number of entries to load (for smoke tests)

    Returns:
        List of question entries with haystack sessions.
    """
    with open(data_file) as f:
        data = json.load(f)

    if limit is not None:
        data = data[:limit]

    logger.info(f"Loaded {len(data)} entries from {data_file}")
    return data


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def map_question_type_to_category(question_type: str) -> str:
    """Map LongMemEval question_type to our 5-category taxonomy."""
    return QUESTION_TYPE_TO_CATEGORY.get(question_type, "IE")


def format_session_as_context(
    session_turns: list[dict],
    date: str,
    session_id: str,
) -> str:
    """Format a LongMemEval session into text for Stompy context creation.

    LongMemEval sessions are lists of {"role": "user"/"assistant", "content": "..."}.
    We include the date and session ID for temporal reasoning.
    """
    lines = [f"DATE: {date}", f"SESSION: {session_id}", "CONVERSATION:"]
    for turn in session_turns:
        role = turn["role"]
        content = turn["content"]
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def build_retrieval_prompt(
    contexts: list[str],
    question: str,
    question_type: str,
    is_abstention: bool = False,
    use_cot: bool = False,
) -> str:
    """Build prompt from retrieved Stompy contexts + question.

    Uses question-type-specific prompts to match LongMemEval's evaluation criteria.
    """
    context_block = "\n\n---\n\n".join(contexts) if contexts else "(No relevant conversations found.)"

    if use_cot:
        if question_type == "temporal-reasoning":
            prompt_template = COT_PROMPT_TEMPORAL
        else:
            prompt_template = COT_PROMPT
    else:
        if is_abstention:
            prompt_template = QA_PROMPT_ABSTENTION
        elif question_type == "temporal-reasoning":
            prompt_template = QA_PROMPT_TEMPORAL
        elif question_type == "knowledge-update":
            prompt_template = QA_PROMPT_KNOWLEDGE_UPDATE
        elif question_type == "single-session-preference":
            prompt_template = QA_PROMPT_PREFERENCE
        else:
            prompt_template = QA_PROMPT

    return context_block + "\n\n" + prompt_template.format(question=question)


# ---------------------------------------------------------------------------
# Retrieval log — for research analysis
# ---------------------------------------------------------------------------

@dataclass
class LongMemEvalRetrievalLog:
    """Captures per-question retrieval details for post-hoc analysis."""

    question_id: str
    question: str
    question_type: str
    answer_session_ids: list[str]
    retrieved_session_ids: list[str]
    retrieved_similarities: list[float]
    prediction: str = ""
    ground_truth: str = ""
    # Search diagnostics
    search_mode: str = ""
    vector_count: int = 0
    bm25_count: int = 0
    overlap_count: int = 0
    expanded_query: str = ""
    sub_queries: list[str] = field(default_factory=list)

    @property
    def is_abstention(self) -> bool:
        return "_abs" in self.question_id

    @property
    def category(self) -> str:
        if self.is_abstention:
            return "ABS"
        return map_question_type_to_category(self.question_type)

    def retrieval_recall(self) -> float:
        """Fraction of answer sessions found in retrieved results."""
        if not self.answer_session_ids:
            return 1.0  # No evidence needed (abstention)
        found = set(self.answer_session_ids) & set(self.retrieved_session_ids)
        return len(found) / len(self.answer_session_ids)

    def recall_at_k(self, k: int = 10) -> float:
        """Fraction of answer sessions found in top-k retrieved results."""
        if not self.answer_session_ids:
            return 1.0
        top_k = set(self.retrieved_session_ids[:k])
        found = set(self.answer_session_ids) & top_k
        return len(found) / len(self.answer_session_ids)

    def precision_at_k(self, k: int = 5) -> float:
        """Fraction of top-k results that are answer sessions."""
        if not self.answer_session_ids:
            return 1.0
        top_k = self.retrieved_session_ids[:k]
        if not top_k:
            return 0.0
        hits = sum(1 for s in top_k if s in self.answer_session_ids)
        return hits / len(top_k)

    def mean_reciprocal_rank(self) -> float:
        """Rank of first relevant result (1/rank). 0 if not found."""
        if not self.answer_session_ids:
            return 1.0
        answer_set = set(self.answer_session_ids)
        for i, sid in enumerate(self.retrieved_session_ids):
            if sid in answer_set:
                return 1.0 / (i + 1)
        return 0.0


# ---------------------------------------------------------------------------
# Load haystack sessions to Stompy
# ---------------------------------------------------------------------------

async def load_haystack_to_stompy(
    client: StompyClient,
    entry: dict,
    project: str,
) -> int:
    """Load all haystack sessions for a question as Stompy contexts.

    Each session becomes a separate context with its date and session ID
    preserved for temporal reasoning.

    Returns the number of contexts created.
    """
    question_id = entry["question_id"]
    sessions = entry["haystack_sessions"]
    dates = entry["haystack_dates"]
    session_ids = entry["haystack_session_ids"]

    # Build all context creation tasks
    tasks = []
    for i, (session, date, sid) in enumerate(zip(sessions, dates, session_ids)):
        if not session:
            continue

        content = format_session_as_context(session, date, sid)
        topic = f"{question_id}_sess_{i}_{sid}"

        tasks.append(
            client.create_context(
                content=content,
                topic=topic,
                tags=f"longmemeval,{question_id}",
                priority="reference",
                project=project,
            )
        )

    # Load in parallel batches to avoid overwhelming the API
    BATCH_SIZE = 10
    count = 0
    for batch_start in range(0, len(tasks), BATCH_SIZE):
        batch = tasks[batch_start : batch_start + BATCH_SIZE]
        await asyncio.gather(*batch)
        count += len(batch)

    return count


# ---------------------------------------------------------------------------
# Retrieval pipeline
# ---------------------------------------------------------------------------

async def retrieve_context(
    client: StompyClient,
    question: str,
    question_id: str,
    question_type: str,
    top_k: int = 10,
    project: str = "",
    use_query_expansion: bool = True,
    use_multi_query: bool = True,
) -> tuple[list[str], list[str], list[float], dict]:
    """Search Stompy for relevant sessions.

    Returns (contents, session_ids, similarities, search_meta).
    """
    category = map_question_type_to_category(question_type)
    numeric_cat = CATEGORY_TO_NUMERIC.get(category, 4)

    sub_queries = []
    sub_query_result_map = {}
    expanded_query_used = ""

    if use_multi_query and numeric_cat in (1, 3):
        sub_queries = decompose_query(question, numeric_cat)

        if len(sub_queries) > 1:
            search_tasks = [
                client.search(query=sq, limit=top_k + 5, threshold=0.1, project=project)
                for sq in sub_queries
            ]
            raw_results = await asyncio.gather(*search_tasks, return_exceptions=True)

            results_per_query = []
            for i, raw in enumerate(raw_results):
                if isinstance(raw, Exception):
                    logger.warning(f"Sub-query {i} failed: {raw}")
                    results_per_query.append([])
                else:
                    results_per_query.append(raw.get("results", []))

            all_results = merge_multi_query_results(results_per_query, top_k=top_k + 5)
            first_raw = next(
                (r for r in raw_results if not isinstance(r, Exception)),
                {"search_mode": "", "vector_count": 0, "bm25_count": 0, "overlap_count": 0},
            )
            search_meta_raw = first_raw if isinstance(first_raw, dict) else {}
        else:
            single_query = sub_queries[0]
            sub_queries = []
            if use_query_expansion and numeric_cat in (1, 3):
                single_query = expand_query(single_query, numeric_cat)
            if single_query != question:
                expanded_query_used = single_query
            raw = await client.search(query=single_query, limit=top_k + 5, threshold=0.1, project=project)
            all_results = raw.get("results", [])
            search_meta_raw = raw
    else:
        search_query = question
        if use_query_expansion and numeric_cat in (1, 3):
            search_query = expand_query(question, numeric_cat)
        if search_query != question:
            expanded_query_used = search_query

        raw = await client.search(query=search_query, limit=top_k + 5, threshold=0.1, project=project)
        all_results = raw.get("results", [])
        search_meta_raw = raw

    # Filter to project-only results
    project_results = [r for r in all_results if r.get("source") != "user_global"]

    # Filter to this question's contexts only
    if question_id:
        project_results = [r for r in project_results if question_id in r.get("label", "")]

    # Extract data from results
    contents = []
    session_ids = []
    similarities = []

    for r in project_results[:top_k]:
        content = r.get("content") or r.get("preview", "")
        contents.append(content)
        # Extract original session ID from topic label (format: q_001_sess_0_filler_001)
        label = r.get("label", "")
        # Parse: {question_id}_sess_{idx}_{original_session_id}
        parts = label.split("_sess_")
        if len(parts) >= 2:
            remainder = parts[1]
            # Skip the index number and underscore
            idx_end = remainder.find("_")
            if idx_end >= 0:
                original_sid = remainder[idx_end + 1:]
                session_ids.append(original_sid)
            else:
                session_ids.append(label)
        else:
            session_ids.append(label)
        similarities.append(r.get("rrf_score") or r.get("similarity") or 0.0)

    search_meta = {
        "search_mode": search_meta_raw.get("search_mode", ""),
        "vector_count": search_meta_raw.get("vector_count", 0),
        "bm25_count": search_meta_raw.get("bm25_count", 0),
        "overlap_count": search_meta_raw.get("overlap_count", 0),
        "expanded_query": expanded_query_used,
        "sub_queries": sub_queries,
    }

    return contents, session_ids, similarities, search_meta


# ---------------------------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------------------------

async def run_longmemeval_evaluation(
    data: list[dict],
    model: str = "claude-sonnet",
    top_k: int = 10,
    use_cot: bool = False,
    use_query_expansion: bool = True,
    use_multi_query: bool = True,
) -> tuple[list[dict], list[LongMemEvalRetrievalLog]]:
    """Run Stompy retrieval evaluation on LongMemEval dataset.

    For each question:
    1. Create a Stompy project and load haystack sessions
    2. Wait for embeddings
    3. Search for relevant sessions
    4. Generate answer with Claude
    5. Record prediction and retrieval metrics

    Returns (predictions, retrieval_logs).
    """
    stompy_url = os.environ.get("STOMPY_API_URL", "https://api.stompy.ai")
    stompy_key = os.environ.get("STOMPY_API_KEY", os.environ.get("DEMENTIA_API_KEY", ""))
    if not stompy_key:
        raise ValueError("STOMPY_API_KEY or DEMENTIA_API_KEY must be set")

    predictions = []
    retrieval_logs = []

    for entry in tqdm(data, desc="LongMemEval"):
        question_id = entry["question_id"]
        question = entry["question"]
        question_type = entry["question_type"]
        answer = entry["answer"]
        is_abstention = "_abs" in question_id
        answer_session_ids = entry.get("answer_session_ids", [])

        project_name = make_project_name()
        client = StompyClient(base_url=stompy_url, api_key=stompy_key)

        try:
            # Step 1: Create project and load haystack
            await client.create_project(project_name)
            num_loaded = await load_haystack_to_stompy(client, entry, project=project_name)
            logger.info(f"[{question_id}] Loaded {num_loaded} sessions")

            # Step 2: Wait for embeddings
            await client.wait_for_embeddings(project=project_name)

            # Step 3: Retrieve relevant context
            contents, retrieved_sids, sims, search_meta = await retrieve_context(
                client,
                question,
                question_id,
                question_type,
                top_k=top_k,
                project=project_name,
                use_query_expansion=use_query_expansion,
                use_multi_query=use_multi_query,
            )

            # Step 4: Build prompt and generate answer
            prompt = build_retrieval_prompt(
                contents, question, question_type,
                is_abstention=is_abstention,
                use_cot=use_cot,
            )

            token_budget = LONGMEMEVAL_COT_TOKEN_BUDGET if use_cot else LONGMEMEVAL_TOKEN_BUDGET
            # Retry on transient LLM errors (OpenRouter 5xx)
            raw_answer = None
            for attempt in range(3):
                try:
                    raw_answer = run_llm(prompt, token_budget, model)
                    break
                except Exception as e:
                    if attempt < 2:
                        logger.warning(f"[{question_id}] LLM call failed (attempt {attempt+1}): {e}")
                        await asyncio.sleep(5 * (attempt + 1))
                    else:
                        logger.error(f"[{question_id}] LLM call failed after 3 attempts: {e}")
                        raw_answer = "I don't know"

            # Extract and clean answer
            if use_cot:
                raw_answer = extract_final_answer(raw_answer)
            hypothesis = strip_markdown(raw_answer)
            hypothesis = extract_short_answer(hypothesis)

            predictions.append({
                "question_id": question_id,
                "hypothesis": hypothesis.strip(),
            })

            # Step 5: Log retrieval metrics
            log = LongMemEvalRetrievalLog(
                question_id=question_id,
                question=question,
                question_type=question_type,
                answer_session_ids=answer_session_ids,
                retrieved_session_ids=retrieved_sids,
                retrieved_similarities=sims,
                prediction=hypothesis.strip(),
                ground_truth=answer,
                search_mode=search_meta.get("search_mode", ""),
                vector_count=search_meta.get("vector_count", 0),
                bm25_count=search_meta.get("bm25_count", 0),
                overlap_count=search_meta.get("overlap_count", 0),
                expanded_query=search_meta.get("expanded_query", ""),
                sub_queries=search_meta.get("sub_queries", []),
            )
            retrieval_logs.append(log)

            logger.info(
                f"[{question_id}] type={question_type} "
                f"recall={log.retrieval_recall():.2f} "
                f"pred={hypothesis[:60]!r}"
            )

        finally:
            try:
                await client.delete_project(project_name)
            except Exception as e:
                logger.warning(f"Cleanup failed for {question_id}: {e}")
            await client.close()

    return predictions, retrieval_logs


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def save_predictions_jsonl(predictions: list[dict], output_path: str) -> None:
    """Save predictions in JSONL format for LongMemEval's evaluate_qa.py."""
    with open(output_path, "w") as f:
        for pred in predictions:
            f.write(json.dumps(pred) + "\n")
    logger.info(f"Saved {len(predictions)} predictions to {output_path}")


def save_retrieval_analysis(
    logs: list[LongMemEvalRetrievalLog],
    output_path: str,
) -> dict:
    """Aggregate retrieval metrics and save to JSON for research analysis."""
    from collections import defaultdict

    analysis = {
        "total_questions": len(logs),
        "by_category": {},
        "overall_retrieval_recall": 0.0,
        "retrieval_metrics": {},
        "questions": [],
    }

    cat_recalls = defaultdict(list)
    all_recalls = []
    all_mrr = []
    all_p5 = []
    all_r5 = []
    all_r10 = []

    for log in logs:
        recall = log.retrieval_recall()
        cat = log.category
        cat_recalls[cat].append(recall)
        all_recalls.append(recall)
        all_mrr.append(log.mean_reciprocal_rank())
        all_p5.append(log.precision_at_k(5))
        all_r5.append(log.recall_at_k(5))
        all_r10.append(log.recall_at_k(10))

        analysis["questions"].append({
            "question_id": log.question_id,
            "question": log.question,
            "question_type": log.question_type,
            "category": cat,
            "is_abstention": log.is_abstention,
            "answer_session_ids": log.answer_session_ids,
            "retrieved_session_ids": log.retrieved_session_ids,
            "retrieved_similarities": log.retrieved_similarities,
            "retrieval_recall": round(recall, 3),
            "recall_at_5": round(log.recall_at_k(5), 3),
            "recall_at_10": round(log.recall_at_k(10), 3),
            "mrr": round(log.mean_reciprocal_rank(), 3),
            "prediction": log.prediction,
            "ground_truth": log.ground_truth,
            "search_mode": log.search_mode,
            "expanded_query": log.expanded_query,
            "sub_queries": log.sub_queries,
        })

    for cat, recalls in sorted(cat_recalls.items()):
        avg = sum(recalls) / len(recalls) if recalls else 0
        analysis["by_category"][cat] = {
            "count": len(recalls),
            "avg_retrieval_recall": round(avg, 3),
        }

    n = len(logs) or 1
    analysis["overall_retrieval_recall"] = round(sum(all_recalls) / n, 3)
    analysis["retrieval_metrics"] = {
        "avg_mrr": round(sum(all_mrr) / n, 3),
        "avg_precision_at_5": round(sum(all_p5) / n, 3),
        "avg_recall_at_5": round(sum(all_r5) / n, 3),
        "avg_recall_at_10": round(sum(all_r10) / n, 3),
    }

    with open(output_path, "w") as f:
        json.dump(analysis, f, indent=2)

    logger.info(f"Retrieval analysis saved to {output_path}")
    return analysis


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run LongMemEval with Stompy retrieval")
    parser.add_argument("--data-file", required=True, help="Path to longmemeval_s_cleaned.json")
    parser.add_argument("--out-dir", required=True, help="Output directory")
    parser.add_argument("--model", default="claude-sonnet", help="LLM model name")
    parser.add_argument("--top-k", type=int, default=10, help="Top-K retrieval results")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of questions (for smoke tests)")
    parser.add_argument("--use-cot", action="store_true", help="Use chain-of-thought prompts")
    parser.add_argument("--no-query-expansion", action="store_true", help="Disable query expansion")
    parser.add_argument("--no-multi-query", action="store_true", help="Disable multi-query decomposition")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    # Load dataset
    data = load_longmemeval_dataset(args.data_file, limit=args.limit)

    # Create output directory
    os.makedirs(args.out_dir, exist_ok=True)

    # Run evaluation
    predictions, retrieval_logs = asyncio.run(
        run_longmemeval_evaluation(
            data,
            model=args.model,
            top_k=args.top_k,
            use_cot=args.use_cot,
            use_query_expansion=not args.no_query_expansion,
            use_multi_query=not args.no_multi_query,
        )
    )

    # Save outputs
    suffix = f"top{args.top_k}"
    if args.use_cot:
        suffix += "_cot"

    predictions_file = os.path.join(args.out_dir, f"stompy_predictions_{suffix}.jsonl")
    save_predictions_jsonl(predictions, predictions_file)

    analysis_file = os.path.join(args.out_dir, f"stompy_retrieval_analysis_{suffix}.json")
    analysis = save_retrieval_analysis(retrieval_logs, analysis_file)

    # Print summary
    print(f"\n=== LongMemEval Stompy Results (top_k={args.top_k}) ===")
    print(f"Questions evaluated: {analysis['total_questions']}")
    print(f"Overall retrieval recall: {analysis['overall_retrieval_recall']}")
    print(f"MRR: {analysis['retrieval_metrics']['avg_mrr']}")
    print(f"Recall@5: {analysis['retrieval_metrics']['avg_recall_at_5']}")
    print(f"Recall@10: {analysis['retrieval_metrics']['avg_recall_at_10']}")
    print(f"\nBy category:")
    for cat, stats in sorted(analysis["by_category"].items()):
        print(f"  {cat}: recall={stats['avg_retrieval_recall']} (n={stats['count']})")

    print(f"\nPredictions: {predictions_file}")
    print(f"Analysis:    {analysis_file}")
    print(f"\nTo evaluate with GPT-4o judge:")
    print(f"  cd longmemeval_data/src/evaluation")
    print(f"  python3 evaluate_qa.py gpt-4o {predictions_file} {args.data_file}")


if __name__ == "__main__":
    main()
