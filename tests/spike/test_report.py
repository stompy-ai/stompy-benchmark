from spike.report import build_report


def rows():
    return [
        {
            "condition": c,
            "repeat": n,
            "outcome": "OK",
            "score": 5,
            "max_score": 5,
            "critical_passed": True,
            "cost_usd": 1.0,
        }
        for n in [1, 2]
        for c in ["stompy", "nomemory"]
    ]


def report(data, after="a" * 40):
    return build_report(data, repeats=2, before="a" * 40, after=after, hashes={})


def test_build_drift_or_missing_row_cannot_be_valid():
    assert report(rows(), "b" * 40)["outcome"] == "INCONCLUSIVE"
    assert report(rows()[:3])["outcome"] == "INCONCLUSIVE"


def test_invalid_row_never_enters_paired_delta():
    data = rows()
    data[0].update(outcome="INVALID", score=None, cost_usd=None)
    r = report(data)
    assert len(r["paired_deltas"]) == 1
    assert r["known_agent_cost_usd"] == 3 and r["agent_cost_complete"] is False


def test_valid_report_control():
    r = report(rows())
    assert r["outcome"] == "VALID" and r["nomemory_saturates"] is True
    assert len(r["paired_deltas"]) == 2
