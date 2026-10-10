# STOMPY-2699 shadow spike

Outcome: **INCONCLUSIVE**

project key, team project on MAIN, owner 51/admin. This proves nothing about routed tenants.

Server before: `7389ece91bd6911c0b6030c2f47a991c494ebcd4`; after: `84e18faada491cbf5bf8c3d4c03a62c964765109`.
Matrix: 1/4 rows; valid=False.
Known agent cost: $1.7509; complete=False.

| Condition | Repeat | Outcome | Score | Cost | Reason |
|---|---:|---|---:|---:|---|
| stompy | 1 | INVALID | None | $1.7509 | server build drift after cell |

Paired deltas (Stompy − nomemory):
```json
[]
```

Nomemory saturates: None

Hashes:
```json
{
  "prompt": "1d192479488d59b9b90b4c68d5327e98705e41283c7d81ad4bf6829e64587539",
  "fixture": "aea1b09a3e282db1212bbcfd3a08d16cca15a7dc0a77b687ce2b05e04ac3d2eb",
  "scorer": "136537e902840b326e8edfdb3e03640156c9f6a10e74d8b6b828c5699408e694",
  "harness": "36f0f13b0ca870ae6331c0c83c6baeaa44eec91ac6ac2101c433d7aea9f96cce",
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
      "agent-a9edfabcd95c09931": {},
      "lead": {
        "stompy": 2
      },
      "toolu_01XJeZ2HUN3agVo8Fvvuh2TM": {}
    }
  }
]
```
