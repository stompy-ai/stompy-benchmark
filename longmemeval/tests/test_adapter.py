"""
Tests for LongMemEval → Stompy adapter.

Follows the same pattern as test_stompy_utils.py: all HTTP calls are mocked,
tests use fixed data, and each test is independent.
"""

import sys
from pathlib import Path

# Add longmemeval dir and locomo/task_eval to path
_LONGMEMEVAL_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(_LONGMEMEVAL_DIR))
sys.path.insert(0, str(_LONGMEMEVAL_DIR.parent / "locomo" / "task_eval"))

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from adapter import (
    load_longmemeval_dataset,
    format_session_as_context,
    map_question_type_to_category,
    build_retrieval_prompt,
    load_haystack_to_stompy,
    LongMemEvalRetrievalLog,
    run_longmemeval_evaluation,
    save_predictions_jsonl,
    save_retrieval_analysis,
    QUESTION_TYPE_TO_CATEGORY,
)


# ---------------------------------------------------------------------------
# Fixed test data — mirrors LongMemEval dataset format
# ---------------------------------------------------------------------------

SAMPLE_ENTRY = {
    "question_id": "q_001",
    "question_type": "single-session-user",
    "question": "What degree did I graduate with?",
    "answer": "Business Administration",
    "question_date": "2023/05/30 (Tue) 23:40",
    "haystack_session_ids": ["filler_001", "answer_abc123", "filler_002"],
    "haystack_dates": [
        "2023/05/20 (Sat) 10:00",
        "2023/05/22 (Mon) 14:30",
        "2023/05/25 (Thu) 09:15",
    ],
    "haystack_sessions": [
        [
            {"role": "user", "content": "Tell me about the weather today."},
            {"role": "assistant", "content": "It looks sunny!"},
        ],
        [
            {"role": "user", "content": "I just graduated with a degree in Business Administration!"},
            {"role": "assistant", "content": "Congratulations! That's a great achievement.", "has_answer": True},
        ],
        [
            {"role": "user", "content": "What's a good recipe for pasta?"},
            {"role": "assistant", "content": "Try aglio e olio — garlic, olive oil, chili flakes."},
        ],
    ],
    "answer_session_ids": ["answer_abc123"],
}

SAMPLE_ENTRY_ABSTENTION = {
    "question_id": "q_002_abs",
    "question_type": "single-session-user",
    "question": "What is my favorite color?",
    "answer": "Not mentioned in the conversation history",
    "question_date": "2023/06/01 (Thu) 12:00",
    "haystack_session_ids": ["filler_003"],
    "haystack_dates": ["2023/05/28 (Sun) 16:00"],
    "haystack_sessions": [
        [
            {"role": "user", "content": "How do I reset my password?"},
            {"role": "assistant", "content": "Go to Settings > Account > Reset Password."},
        ],
    ],
    "answer_session_ids": [],
}

SAMPLE_ENTRY_MULTI_SESSION = {
    "question_id": "q_003",
    "question_type": "multi-session",
    "question": "What city did I move to after leaving New York?",
    "answer": "San Francisco",
    "question_date": "2023/07/15 (Sat) 18:00",
    "haystack_session_ids": ["answer_sess_1", "filler_004", "answer_sess_2"],
    "haystack_dates": [
        "2023/06/01 (Thu) 10:00",
        "2023/06/15 (Thu) 14:00",
        "2023/07/01 (Sat) 09:00",
    ],
    "haystack_sessions": [
        [
            {"role": "user", "content": "I'm planning to leave New York soon."},
            {"role": "assistant", "content": "Where are you thinking of moving?", "has_answer": True},
        ],
        [
            {"role": "user", "content": "What's the best way to learn Python?"},
            {"role": "assistant", "content": "Try the official tutorial first."},
        ],
        [
            {"role": "user", "content": "I finally moved to San Francisco!"},
            {"role": "assistant", "content": "That's exciting! How do you like it?", "has_answer": True},
        ],
    ],
    "answer_session_ids": ["answer_sess_1", "answer_sess_2"],
}

SAMPLE_DATASET = [SAMPLE_ENTRY, SAMPLE_ENTRY_ABSTENTION, SAMPLE_ENTRY_MULTI_SESSION]


# ---------------------------------------------------------------------------
# Test: Dataset loading
# ---------------------------------------------------------------------------

class TestLoadDataset:
    def test_loads_all_entries(self, tmp_path):
        data_file = tmp_path / "test_data.json"
        data_file.write_text(json.dumps(SAMPLE_DATASET))

        entries = load_longmemeval_dataset(str(data_file))
        assert len(entries) == 3

    def test_loads_with_limit(self, tmp_path):
        data_file = tmp_path / "test_data.json"
        data_file.write_text(json.dumps(SAMPLE_DATASET))

        entries = load_longmemeval_dataset(str(data_file), limit=2)
        assert len(entries) == 2

    def test_entry_has_required_fields(self, tmp_path):
        data_file = tmp_path / "test_data.json"
        data_file.write_text(json.dumps([SAMPLE_ENTRY]))

        entries = load_longmemeval_dataset(str(data_file))
        entry = entries[0]
        assert entry["question_id"] == "q_001"
        assert entry["question_type"] == "single-session-user"
        assert entry["question"] == "What degree did I graduate with?"
        assert entry["answer"] == "Business Administration"
        assert len(entry["haystack_sessions"]) == 3
        assert len(entry["answer_session_ids"]) == 1

    def test_identifies_abstention_questions(self, tmp_path):
        data_file = tmp_path / "test_data.json"
        data_file.write_text(json.dumps([SAMPLE_ENTRY_ABSTENTION]))

        entries = load_longmemeval_dataset(str(data_file))
        assert "_abs" in entries[0]["question_id"]


# ---------------------------------------------------------------------------
# Test: Session formatting
# ---------------------------------------------------------------------------

class TestFormatSession:
    def test_formats_user_assistant_turns(self):
        session = [
            {"role": "user", "content": "Hello there!"},
            {"role": "assistant", "content": "Hi! How can I help?"},
        ]
        result = format_session_as_context(session, "2023/05/20 (Sat) 10:00", "sess_1")
        assert "DATE: 2023/05/20 (Sat) 10:00" in result
        assert "user: Hello there!" in result
        assert "assistant: Hi! How can I help?" in result

    def test_preserves_session_id(self):
        session = [{"role": "user", "content": "Test"}]
        result = format_session_as_context(session, "2023/01/01", "my_session")
        assert "SESSION: my_session" in result

    def test_handles_empty_session(self):
        result = format_session_as_context([], "2023/01/01", "empty")
        assert "DATE:" in result
        assert "SESSION:" in result

    def test_strips_has_answer_field(self):
        """has_answer is metadata, not content — should not leak into context."""
        session = [
            {"role": "user", "content": "I graduated!", "has_answer": True},
        ]
        result = format_session_as_context(session, "2023/01/01", "sess_1")
        assert "has_answer" not in result


# ---------------------------------------------------------------------------
# Test: Question type mapping
# ---------------------------------------------------------------------------

class TestQuestionTypeMapping:
    def test_maps_single_session_user(self):
        assert map_question_type_to_category("single-session-user") == "IE"

    def test_maps_multi_session(self):
        assert map_question_type_to_category("multi-session") == "MR"

    def test_maps_temporal_reasoning(self):
        assert map_question_type_to_category("temporal-reasoning") == "TR"

    def test_maps_knowledge_update(self):
        assert map_question_type_to_category("knowledge-update") == "KU"

    def test_maps_abstention_by_question_id(self):
        # Abstention is determined by question_id suffix "_abs", not type
        # So the type mapping just maps the base type
        assert map_question_type_to_category("single-session-user") == "IE"

    def test_maps_single_session_preference(self):
        assert map_question_type_to_category("single-session-preference") == "IE"

    def test_maps_single_session_assistant(self):
        assert map_question_type_to_category("single-session-assistant") == "IE"


# ---------------------------------------------------------------------------
# Test: Prompt building
# ---------------------------------------------------------------------------

class TestBuildRetrievalPrompt:
    def test_includes_context_and_question(self):
        contexts = ["DATE: 2023/05/22\nuser: I graduated with a BA."]
        prompt = build_retrieval_prompt(contexts, "What degree?", "single-session-user")
        assert "I graduated with a BA" in prompt
        assert "What degree?" in prompt

    def test_abstention_prompt_differs(self):
        contexts = ["Some context"]
        normal = build_retrieval_prompt(contexts, "Q?", "single-session-user")
        abstention = build_retrieval_prompt(contexts, "Q?", "single-session-user", is_abstention=True)
        # Abstention prompt should mention inability to find info
        assert normal != abstention

    def test_temporal_prompt_includes_date_hint(self):
        contexts = ["Some context"]
        prompt = build_retrieval_prompt(contexts, "When?", "temporal-reasoning")
        assert "date" in prompt.lower() or "time" in prompt.lower()


# ---------------------------------------------------------------------------
# Test: RetrievalLog
# ---------------------------------------------------------------------------

class TestRetrievalLog:
    def test_retrieval_recall_single_session(self):
        log = LongMemEvalRetrievalLog(
            question_id="q_001",
            question="What degree?",
            question_type="single-session-user",
            answer_session_ids=["answer_abc123"],
            retrieved_session_ids=["filler_001", "answer_abc123", "filler_002"],
            retrieved_similarities=[0.9, 0.8, 0.7],
        )
        assert log.retrieval_recall() == 1.0

    def test_retrieval_recall_partial(self):
        log = LongMemEvalRetrievalLog(
            question_id="q_003",
            question="What city?",
            question_type="multi-session",
            answer_session_ids=["answer_sess_1", "answer_sess_2"],
            retrieved_session_ids=["answer_sess_1", "filler_004"],
            retrieved_similarities=[0.9, 0.5],
        )
        assert log.retrieval_recall() == 0.5

    def test_retrieval_recall_none_found(self):
        log = LongMemEvalRetrievalLog(
            question_id="q_001",
            question="What degree?",
            question_type="single-session-user",
            answer_session_ids=["answer_abc123"],
            retrieved_session_ids=["filler_001", "filler_002"],
            retrieved_similarities=[0.5, 0.3],
        )
        assert log.retrieval_recall() == 0.0

    def test_retrieval_recall_abstention(self):
        """Abstention questions have no answer sessions — recall should be 1.0."""
        log = LongMemEvalRetrievalLog(
            question_id="q_002_abs",
            question="What color?",
            question_type="single-session-user",
            answer_session_ids=[],
            retrieved_session_ids=["filler_003"],
            retrieved_similarities=[0.3],
        )
        assert log.retrieval_recall() == 1.0

    def test_recall_at_k(self):
        log = LongMemEvalRetrievalLog(
            question_id="q_003",
            question="What city?",
            question_type="multi-session",
            answer_session_ids=["answer_sess_1", "answer_sess_2"],
            retrieved_session_ids=["filler_001", "answer_sess_2", "filler_002", "answer_sess_1"],
            retrieved_similarities=[0.9, 0.8, 0.7, 0.6],
        )
        # At k=1: only filler_001 → 0/2 = 0.0
        assert log.recall_at_k(1) == 0.0
        # At k=2: filler_001, answer_sess_2 → 1/2 = 0.5
        assert log.recall_at_k(2) == 0.5
        # At k=4: all → 2/2 = 1.0
        assert log.recall_at_k(4) == 1.0

    def test_is_abstention(self):
        log = LongMemEvalRetrievalLog(
            question_id="q_002_abs",
            question="What color?",
            question_type="single-session-user",
            answer_session_ids=[],
            retrieved_session_ids=[],
            retrieved_similarities=[],
        )
        assert log.is_abstention is True

        log2 = LongMemEvalRetrievalLog(
            question_id="q_001",
            question="What degree?",
            question_type="single-session-user",
            answer_session_ids=["answer_abc123"],
            retrieved_session_ids=[],
            retrieved_similarities=[],
        )
        assert log2.is_abstention is False

    def test_category_property(self):
        log = LongMemEvalRetrievalLog(
            question_id="q_001",
            question="What?",
            question_type="temporal-reasoning",
            answer_session_ids=[],
            retrieved_session_ids=[],
            retrieved_similarities=[],
        )
        assert log.category == "TR"


# ---------------------------------------------------------------------------
# Test: Haystack loading to Stompy
# ---------------------------------------------------------------------------

class TestLoadHaystackToStompy:
    @pytest.mark.asyncio
    async def test_creates_contexts_for_each_session(self):
        mock_client = AsyncMock()
        mock_client.create_context = AsyncMock(return_value={"id": "ctx_1"})

        entry = SAMPLE_ENTRY
        count = await load_haystack_to_stompy(
            mock_client,
            entry,
            project="test_project",
        )

        # Should create one context per haystack session
        assert count == 3
        assert mock_client.create_context.call_count == 3

    @pytest.mark.asyncio
    async def test_topic_naming(self):
        mock_client = AsyncMock()
        mock_client.create_context = AsyncMock(return_value={"id": "ctx_1"})

        entry = SAMPLE_ENTRY
        await load_haystack_to_stompy(mock_client, entry, project="test_project")

        # Check topic names include question_id and session index
        calls = mock_client.create_context.call_args_list
        topics = [call.kwargs.get("topic", call.args[1] if len(call.args) > 1 else "") for call in calls]
        # Should use session IDs from the dataset
        for call in calls:
            topic = call.kwargs.get("topic", "")
            assert "q_001" in topic


# ---------------------------------------------------------------------------
# Test: Predictions JSONL output
# ---------------------------------------------------------------------------

class TestSavePredictions:
    def test_writes_jsonl_format(self, tmp_path):
        predictions = [
            {"question_id": "q_001", "hypothesis": "Business Administration"},
            {"question_id": "q_002_abs", "hypothesis": "I don't have that information."},
        ]
        out_file = tmp_path / "predictions.jsonl"
        save_predictions_jsonl(predictions, str(out_file))

        lines = out_file.read_text().strip().split("\n")
        assert len(lines) == 2

        entry = json.loads(lines[0])
        assert entry["question_id"] == "q_001"
        assert entry["hypothesis"] == "Business Administration"


# ---------------------------------------------------------------------------
# Test: Retrieval analysis output
# ---------------------------------------------------------------------------

class TestSaveRetrievalAnalysis:
    def test_aggregates_by_category(self, tmp_path):
        logs = [
            LongMemEvalRetrievalLog(
                question_id="q_001",
                question="What degree?",
                question_type="single-session-user",
                answer_session_ids=["answer_abc"],
                retrieved_session_ids=["answer_abc", "filler"],
                retrieved_similarities=[0.9, 0.5],
                prediction="Business Administration",
                ground_truth="Business Administration",
            ),
            LongMemEvalRetrievalLog(
                question_id="q_003",
                question="What city?",
                question_type="multi-session",
                answer_session_ids=["answer_s1", "answer_s2"],
                retrieved_session_ids=["answer_s1"],
                retrieved_similarities=[0.8],
                prediction="San Francisco",
                ground_truth="San Francisco",
            ),
        ]

        out_file = tmp_path / "analysis.json"
        analysis = save_retrieval_analysis(logs, str(out_file))

        assert analysis["total_questions"] == 2
        assert "IE" in analysis["by_category"]
        assert "MR" in analysis["by_category"]
        assert analysis["by_category"]["IE"]["count"] == 1
        assert analysis["by_category"]["IE"]["avg_retrieval_recall"] == 1.0
        assert analysis["by_category"]["MR"]["count"] == 1
        assert analysis["by_category"]["MR"]["avg_retrieval_recall"] == 0.5

        # Verify file was written
        saved = json.loads(out_file.read_text())
        assert saved["total_questions"] == 2
