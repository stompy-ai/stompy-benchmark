"""Harness-only verification guidance shared verbatim by both task arms.

The task artifact stays pinned; this text is included in the harness hash and
the rendered prompt hash. Modules below exist in snapshot c40570b2.
"""

VERIFICATION = """
Focused verification (both conditions):
Run only the tests relevant to this lifecycle change: start with
python3 -m pytest tests/unit/test_lifecycle_changelog.py tests/unit/test_set_lifecycle_did_you_mean_1879.py -q
and the focused REST/MCP test modules you and your teammate add or modify.
Do not run the full suite or the entire tests/unit/ directory. Do not install
additional dependencies or start external services to run unrelated tests.
If a focused test is blocked by the frozen environment, record the exact blocker
and finish with the checks you could run. Stop after focused verification and
return a concise result with the changed files and test outcomes.
"""
