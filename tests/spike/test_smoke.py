from spike.smoke import isolation


def test_lead_use_alone_is_not_a_teammate_isolation_proof():
    row = {
        "delegated_calls": 1,
        "delegate_trace_map": {"call": "agent-child"},
        "tool_histograms": {"lead": {"stompy": 1}, "agent-child": {}},
    }
    assert not isolation(row)
    row["tool_histograms"]["agent-child"] = {"stompy": 1}
    assert isolation(row)
    row["tool_histograms"]["agent-child"]["operator"] = 1
    assert not isolation(row)
