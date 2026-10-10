import copy

import pytest

from spike.fixture import assert_fixture, fixture_lock


def fixture():
    return {
        "contexts": [
            {
                "label": "rule",
                "version": "1.0",
                "content": "original",
                "priority": "reference",
                "lifecycle": "active",
            }
        ],
        "links": [],
        "tickets": [
            {
                "title": "task",
                "description": "body",
                "status": "done",
                "type": "task",
                "priority": "high",
            }
        ],
    }


@pytest.mark.parametrize("field,value", [("content", "polluted"), ("version", "2.0")])
def test_full_context_diff_refuses_before_launch(field, value):
    expected = fixture()
    actual = copy.deepcopy(expected)
    actual["contexts"][0][field] = value
    with pytest.raises(ValueError, match="read-back differs"):
        assert_fixture(expected, actual)


def test_ticket_body_and_status_and_links_are_checked():
    expected = fixture()
    for field in ["description", "status"]:
        actual = copy.deepcopy(expected)
        actual["tickets"][0][field] = "changed"
        with pytest.raises(ValueError):
            assert_fixture(expected, actual)
    actual = copy.deepcopy(expected)
    actual["links"] = [{"source_label": "rule", "target_label": "answer"}]
    with pytest.raises(ValueError):
        assert_fixture(expected, actual)


def test_lock_serializes_fixture(tmp_path):
    with fixture_lock(tmp_path / "fixture.lock"):
        with pytest.raises(ValueError, match="locked"):
            with fixture_lock(tmp_path / "fixture.lock"):
                pass


def test_exact_fixture_control():
    assert_fixture(fixture(), fixture())
