Implement a REST door for the existing MCP set_lifecycle capability in this frozen Stompy backend.

Expose POST /api/v1/projects/{name}/contexts/{topic}/lifecycle with a JSON body containing state (active, parked, delivered, archived), optional review_after_days and note. Return the existing lifecycle result as JSON. Reuse the existing async stompy_server.set_lifecycle callable as the transition boundary after REST authorization; do not duplicate its storage logic. Preserve MCP behavior, the existing owner/project scoping, write-role checks, missing-topic errors, parking review clock, and idempotence. Invalid state is 422; missing topic is 404; authorization failures must remain refusals. Register the route in the real API router and update context.lifecycle in surface_contract.json while keeping a reasoned CLI waiver. Do not modify unrelated production behavior. New modules must stay under 500 lines; do not raise file-size baselines.

Add tests for both doors. Use one teammate/subagent to implement or review tests while you implement the route, then integrate and run the tests. Leave the solution in /work. You have a limited budget, so focus on this task. Treat the snapshot as the source at its pinned revision; do not fetch repository history or a newer solution from the internet.

{{MEMORY_INSTRUCTION}}
