# STOMPY-2699 shadow spike

Outcome: **VALID**

project key, team project on MAIN, owner 51/admin. This proves nothing about routed tenants.

Server before: `47d3e9016b2dec3b62a778aa9df4294ded565f81`; after: `47d3e9016b2dec3b62a778aa9df4294ded565f81`.
Matrix: 4/4 rows; valid=True.
Known agent cost: $8.8452; complete=True.

| Condition | Repeat | Outcome | Score | Cost | Reason |
|---|---:|---|---:|---:|---|
| stompy | 1 | TASK_FAIL | 4 | $2.6278 | task requires delegation; lead worked alone |
| nomemory | 1 | TASK_FAIL | 4 | $2.2972 |  |
| nomemory | 2 | TASK_FAIL | 4 | $1.8504 |  |
| stompy | 2 | TASK_FAIL | 4 | $2.0698 |  |

Paired deltas (Stompy − nomemory):
```json
[
  {
    "repeat": 1,
    "score_stompy_minus_nomemory": 0,
    "cost_stompy_minus_nomemory": 0.330549
  },
  {
    "repeat": 2,
    "score_stompy_minus_nomemory": 0,
    "cost_stompy_minus_nomemory": 0.219352
  }
]
```

Nomemory saturates: False

Hashes:
```json
{
  "prompt": "1d192479488d59b9b90b4c68d5327e98705e41283c7d81ad4bf6829e64587539",
  "fixture": "aea1b09a3e282db1212bbcfd3a08d16cca15a7dc0a77b687ce2b05e04ac3d2eb",
  "scorer": "136537e902840b326e8edfdb3e03640156c9f6a10e74d8b6b828c5699408e694",
  "harness": "7126a1c2b4dd42d589c41115f36be37eb5d55ee1e894bc4f695874f66e8eb642",
  "snapshot_sha": "c40570b266df628ed1f5a9260ba77096d8bfe71a"
}
```

n=2 raw matched-repeat deltas only; no CIs or causal claim. Historical comparisons confound provider/model drift.
Missing terminal costs remain unknown. Stompy-side embedding/worker costs are not metered by this spike.
Full logical fixture compared; archived contexts and parked tickets remain in product history.
Tests exercise REST runtime contract and resolver decisions with controlled private storage/tool seams. The three critical authorization checks are path-coupled to resolver internals. The real MCP callable and lifecycle SQL are not executed by these oracles; both-door test quality is not scored. Optional review_after_days/note bounds are outside this spike oracle.

Per-actor MCP tool-call histograms:
```json
[
  {
    "condition": "stompy",
    "repeat": 1,
    "actors": {
      "lead": {
        "stompy": 3
      }
    }
  },
  {
    "condition": "nomemory",
    "repeat": 1,
    "actors": {
      "agent-a2fefb9935f80e8ea": {},
      "agent-a66b213608ecc3dae": {},
      "lead": {},
      "toolu_01HpGb4myRBaCaF2ZUwbSSZn": {},
      "toolu_01QrzELbfdD69CMmhodoTJL8": {}
    }
  },
  {
    "condition": "nomemory",
    "repeat": 2,
    "actors": {
      "agent-ab312532ad08e75f0": {},
      "lead": {},
      "toolu_01T87vXxRC69c9TWQFeEXxx8": {}
    }
  },
  {
    "condition": "stompy",
    "repeat": 2,
    "actors": {
      "agent-aae5bbbd4e265d4d6": {},
      "lead": {
        "stompy": 2
      },
      "toolu_019Ftrh5JsKJruP2rKV5zF7P": {}
    }
  }
]
```
