You are the LEAD agent on the Meridian Logistics API in /work. Read SPEC.md. The
project is a bare skeleton; dependencies are already installed in node_modules
and there is no network. Node 22, TypeScript strict, Express 4, better-sqlite3,
Vitest. Run tests with `./node_modules/.bin/vitest run`; type-check with
`./node_modules/.bin/tsc --noEmit` (run the binaries from node_modules/.bin directly).

The feature is delivered in two parts by two different agents. You do PART ONE
only. A fresh agent with no transcript, no chat history and no memory of this
session will do PART TWO after you stop. It sees the repository you leave and
{{HANDOVER_CHANNEL}}.

PART ONE (yours): the foundation.
- `src/types/index.ts`: shared types (roles, statuses, shipment, hub, event).
- `src/utils/response.ts`: the success/error envelope from SPEC.md.
- `src/utils/id.ts`: `MRD-` + 8-char nanoid.
- `src/db.ts`: open a better-sqlite3 database (path argument, default
  `:memory:`), create the three tables from SPEC.md and insert the seed hubs.
- `src/middleware/auth.ts`: the X-Meridian-Auth token. The user has refined the
  SPEC token format: it is
  `base64(org_id:user_id:role:expiry_epoch:hmac_sha256)` where the HMAC-SHA256
  (hex) is over `org_id:user_id:role:expiry_epoch` with the secret from
  `MERIDIAN_AUTH_SECRET`. Role is one of operator, dispatcher, admin. Missing or
  malformed token is AUTH_INVALID 401, expired is AUTH_EXPIRED 401, wrong role
  is AUTH_FORBIDDEN 403. Attach `{ org_id, user_id, role }` to the request.
- Hubs: `src/models/hub.model.ts`, `src/services/hub.service.ts`,
  `src/routes/hub.routes.ts` implementing GET and POST /api/v1/hubs exactly as
  specified.
- `src/app.ts`: `export function createApp(dbPath = ':memory:'): express.Express`
  mounting every route under /api/v1 with JSON body parsing and the error
  envelope for unknown routes (NOT_FOUND 404). `src/index.ts` listens on
  PORT (default 3000). Part two will add the shipment routes to this app.
- A focused Vitest file for the hubs routes and the auth middleware.

PART TWO (not yours; the next agent does it): POST/GET /api/v1/shipments,
GET /api/v1/shipments/:id with events, and PATCH /api/v1/shipments/:id/transition.

DECISIONS THE USER MADE IN THIS SESSION. They override SPEC.md and they all
concern PART TWO, so nothing in the code you write will reveal them. The next
agent must honour them, and it can only know them from what you record.
1. Event order: `events` in GET /api/v1/shipments/:id is returned NEWEST FIRST
   (descending changed_at), not oldest first as the SPEC example shows.
2. Role tightening: the IN_TRANSIT -> AT_HUB transition is dispatcher or admin
   only. Operators may NOT perform it (AUTH_FORBIDDEN 403). The SPEC table is
   wrong on this row; the user changed it today.
3. Pagination: a `limit` query parameter above 100 (or below 1) on
   GET /api/v1/shipments is rejected with VALIDATION_ERROR 400 and the message
   `limit must be between 1 and 100`. It is never silently clamped.

When part one type-checks and its tests pass, record the handover for the next
agent ({{RECORDING_INSTRUCTION}}), then call done with a short summary.
