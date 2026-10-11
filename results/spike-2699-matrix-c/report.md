# STOMPY-2699 shadow spike

Outcome: **INCONCLUSIVE**

project key, team project on MAIN, owner 51/admin. This proves nothing about routed tenants.

Server before: `8602947abab765bbfbcc105e03416de72953e15d`; after: `8602947abab765bbfbcc105e03416de72953e15d`.
Matrix: 1/4 rows; valid=False.
Known agent cost: $0.0000; complete=False.

| Condition | Repeat | Outcome | Score | Cost | Reason |
|---|---:|---|---:|---:|---|
| stompy | 1 | INVALID | None | unknown | missing terminal result |

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
  "harness": "79df756214e2727503972e8a22cd87f69ac98076943dead441efa0c79718c4eb",
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
      "agent-a36560bb757bebc04": {},
      "lead": {
        "stompy": 3
      },
      "toolu_01GZgbREtBouPPLmffWD3SYG": {},
      "toolu_01Tsyrd2UnNzqegTRcLPafxv": {},
      "toolu_01UNapjfrozFt5hus2sAcDNZ": {}
    }
  }
]
```
