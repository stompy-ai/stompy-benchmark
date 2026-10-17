You are a fresh agent taking over the Meridian Logistics API in /work. Read
SPEC.md. Another agent already delivered PART ONE (types, envelope, ids,
database, auth middleware, hubs routes, `createApp` in src/app.ts). You have no
transcript of that session. Dependencies are installed; there is no network.
Node 22, TypeScript strict, Express 4, better-sqlite3, Vitest. Run tests with
`./node_modules/.bin/vitest run`; type-check with `./node_modules/.bin/tsc --noEmit`
(run the binaries from node_modules/.bin directly).

PART TWO (yours): implement the shipment routes in `src/routes/shipment.routes.ts`
with `src/services/shipment.service.ts` and `src/models/shipment.model.ts`, and
mount them in `createApp`:
- POST /api/v1/shipments
- GET /api/v1/shipments (pagination and filters)
- GET /api/v1/shipments/:id (with the event history)
- PATCH /api/v1/shipments/:id/transition (state machine, events, updated_at)

The user made decisions with the lead agent during part one that refine or
override SPEC.md for part two. {{MEMORY_INSTRUCTION}} Apply every decision you
find; where you find none, follow SPEC.md. Do not ask questions; there is nobody
to answer. Add a focused Vitest file for the shipment routes. When
`./node_modules/.bin/tsc --noEmit` and `./node_modules/.bin/vitest run` pass, call done with a short summary
that names each decision you applied.
