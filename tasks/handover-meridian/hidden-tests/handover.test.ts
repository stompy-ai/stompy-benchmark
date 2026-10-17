// Hidden oracle for scenario C (STOMPY-2798). Copied next to the submission as
// tests/handover.test.ts and run alone. Names are graded individually; the
// three decision_* checks require state the lead agent recorded.
import { test, expect, beforeAll, afterAll } from 'vitest';
import { createHmac } from 'node:crypto';
import { setTimeout as sleep } from 'node:timers/promises';
import type { Server } from 'node:http';
import { createApp } from '../src/app.js';

const SECRET = 'oracle-secret';
process.env.MERIDIAN_AUTH_SECRET = SECRET;

function token(role: string, user = `user_${role}`, org = 'org_oracle', ttlMs = 60_000) {
  const expiry = Date.now() + ttlMs;
  const payload = `${org}:${user}:${role}:${expiry}`;
  const sig = createHmac('sha256', SECRET).update(payload).digest('hex');
  return Buffer.from(`${payload}:${sig}`).toString('base64');
}

let server: Server;
let base = '';

beforeAll(async () => {
  const app = createApp();
  await new Promise<void>((resolve) => {
    server = app.listen(0, '127.0.0.1', () => resolve());
  });
  const address = server.address();
  if (!address || typeof address === 'string') throw new Error('no port');
  base = `http://127.0.0.1:${address.port}`;
});

afterAll(async () => {
  await new Promise<void>((resolve) => server.close(() => resolve()));
});

async function call(method: string, path: string, role: string, body?: unknown) {
  const response = await fetch(base + path, {
    method,
    headers: { 'content-type': 'application/json', 'x-meridian-auth': token(role) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return { status: response.status, json: (await response.json()) as any };
}

async function draft(role = 'operator') {
  const r = await call('POST', '/api/v1/shipments', role, {
    origin_hub: 'LAX', dest_hub: 'JFK', weight_g: 1500, priority: 2,
  });
  expect(r.status).toBe(201);
  return r.json.data.id as string;
}

async function advance(id: string, to_status: string, role = 'dispatcher', extra: object = {}) {
  await sleep(10); // distinct changed_at for the ordering check
  return call('PATCH', `/api/v1/shipments/${id}/transition`, role, { to_status, ...extra });
}

test('hubs_list_is_seeded', async () => {
  const r = await call('GET', '/api/v1/hubs', 'operator');
  expect(r.status).toBe(200);
  expect(r.json.ok).toBe(true);
  expect(r.json.data.map((h: any) => h.code).sort()).toEqual(['DFW', 'JFK', 'LAX', 'MIA', 'ORD']);
});

test('create_shipment_returns_draft_201', async () => {
  const r = await call('POST', '/api/v1/shipments', 'operator', {
    origin_hub: 'LAX', dest_hub: 'ORD', weight_g: 20000, priority: 1, manifest_ref: 'MF-00000001',
  });
  expect(r.status).toBe(201);
  expect(r.json.data.status).toBe('DRAFT');
  expect(r.json.data.id).toMatch(/^MRD-.{8}$/);
  expect(r.json.data.created_by).toBe('user_operator');
  expect(r.json.data.org_id).toBe('org_oracle');
});

test('create_shipment_same_hub_is_400', async () => {
  const r = await call('POST', '/api/v1/shipments', 'operator', {
    origin_hub: 'LAX', dest_hub: 'LAX', weight_g: 100, priority: 3,
  });
  expect(r.status).toBe(400);
  expect(r.json.error.code).toBe('VALIDATION_ERROR');
});

test('unknown_shipment_is_404_not_found', async () => {
  const r = await call('GET', '/api/v1/shipments/MRD-zzzzzzzz', 'operator');
  expect(r.status).toBe(404);
  expect(r.json.error.code).toBe('NOT_FOUND');
});

test('manifest_requires_manifest_ref_400', async () => {
  const id = await draft();
  const r = await advance(id, 'MANIFESTED');
  expect(r.status).toBe(400);
  expect(r.json.error.code).toBe('VALIDATION_ERROR');
});

test('invalid_transition_is_409', async () => {
  const id = await draft();
  const r = await advance(id, 'DELIVERED');
  expect(r.status).toBe(409);
  expect(r.json.error.code).toBe('TRANSITION_ERROR');
});

test('dispatcher_moves_in_transit_to_at_hub', async () => {
  const id = await draft();
  expect((await advance(id, 'MANIFESTED', 'dispatcher', { manifest_ref: 'MF-12345678' })).status).toBe(200);
  expect((await advance(id, 'IN_TRANSIT')).status).toBe(200);
  const r = await advance(id, 'AT_HUB', 'dispatcher');
  expect(r.status).toBe(200);
  expect(r.json.data.status).toBe('AT_HUB');
  expect(r.json.data.event.from_status).toBe('IN_TRANSIT');
});

test('decision_events_newest_first', async () => {
  const id = await draft();
  expect((await advance(id, 'MANIFESTED', 'dispatcher', { manifest_ref: 'MF-00000002' })).status).toBe(200);
  expect((await advance(id, 'IN_TRANSIT')).status).toBe(200);
  const r = await call('GET', `/api/v1/shipments/${id}`, 'operator');
  expect(r.status).toBe(200);
  const events = r.json.data.events;
  expect(events).toHaveLength(2);
  expect(events[0].to_status).toBe('IN_TRANSIT');
  expect(events[1].to_status).toBe('MANIFESTED');
  expect(events[0].changed_at).toBeGreaterThan(events[1].changed_at);
});

test('decision_operator_cannot_move_in_transit_to_at_hub', async () => {
  const id = await draft();
  expect((await advance(id, 'MANIFESTED', 'dispatcher', { manifest_ref: 'MF-00000003' })).status).toBe(200);
  expect((await advance(id, 'IN_TRANSIT')).status).toBe(200);
  const r = await advance(id, 'AT_HUB', 'operator');
  expect(r.status).toBe(403);
  expect(r.json.error.code).toBe('AUTH_FORBIDDEN');
});

test('decision_limit_above_100_is_rejected', async () => {
  const r = await call('GET', '/api/v1/shipments?limit=101', 'operator');
  expect(r.status).toBe(400);
  expect(r.json.error.code).toBe('VALIDATION_ERROR');
  expect(r.json.error.message).toBe('limit must be between 1 and 100');
});
