# STOMPY-2699 shadow spike

Outcome: **INCONCLUSIVE**

project key, team project on MAIN, owner 51/admin. This proves nothing about routed tenants.

Server before: `c40570b266df628ed1f5a9260ba77096d8bfe71a`; after: `c40570b266df628ed1f5a9260ba77096d8bfe71a`.
Matrix: 1/4 rows; valid=False.
Known agent cost: $0.0000; complete=False.

| Condition | Repeat | Outcome | Score | Cost | Reason |
|---|---:|---|---:|---:|---|
| stompy | 1 | INVALID | None | unknown | ValueError: Provider authentication missing |

Paired deltas (Stompy − nomemory):
```json
[]
```

Nomemory saturates: None

Hashes:
```json
{
  "prompt": "1d192479488d59b9b90b4c68d5327e98705e41283c7d81ad4bf6829e64587539",
  "fixture": "0a5ee10361a6a6c316d85a5a2037135a083410892395a61be21a673a165f5386",
  "scorer": "136537e902840b326e8edfdb3e03640156c9f6a10e74d8b6b828c5699408e694",
  "harness": "d39b79193c307c8ceb5f9b1a5b10217d126f079d15a5f73bb2e38e1b1423a1b8",
  "snapshot_sha": "c40570b266df628ed1f5a9260ba77096d8bfe71a"
}
```

n=2 raw matched-repeat deltas only; no CIs or causal claim. Historical comparisons confound provider/model drift.
Missing terminal costs remain unknown. Stompy-side embedding/worker costs are not metered by this spike.
Full logical fixture compared; archived contexts and parked tickets remain in product history.
Tests exercise REST runtime contract and real resolver decisions with controlled storage/tool seams; existing lifecycle SQL is not revalidated.

Per-actor MCP tool-call histograms:
```json
[
  {
    "condition": "stompy",
    "repeat": 1,
    "actors": {}
  }
]
```
