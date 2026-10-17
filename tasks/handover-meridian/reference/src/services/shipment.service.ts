import type { Db } from '../db.js';
import { hubModel } from '../models/hub.model.js';
import { shipmentModel } from '../models/shipment.model.js';
import type { Auth, Role, Shipment, ShipmentEvent, Status } from '../types/index.js';
import { newId } from '../utils/id.js';
import { ApiError } from '../utils/response.js';

const MANIFEST = /^MF-\d{8}$/;
const TERMINAL: Status[] = ['DELIVERED', 'RETURNED'];
const ALL: Role[] = ['operator', 'dispatcher', 'admin'];
const DISPATCH: Role[] = ['dispatcher', 'admin'];
// Decision 2: IN_TRANSIT -> AT_HUB is dispatcher/admin only (SPEC table overridden).
const TRANSITIONS: Record<string, { to: Status; roles: Role[] }[]> = {
  DRAFT: [{ to: 'MANIFESTED', roles: DISPATCH }],
  MANIFESTED: [{ to: 'IN_TRANSIT', roles: DISPATCH }],
  IN_TRANSIT: [{ to: 'AT_HUB', roles: DISPATCH }],
  AT_HUB: [{ to: 'OUT_FOR_DELIVERY', roles: DISPATCH }],
  OUT_FOR_DELIVERY: [{ to: 'DELIVERED', roles: ALL }],
  EXCEPTION: [{ to: 'RETURNED', roles: ['admin'] }],
};

const int = (v: unknown) => (typeof v === 'number' && Number.isInteger(v) ? v : undefined);

export const shipmentService = (db: Db) => {
  const shipments = shipmentModel(db);
  const hubs = hubModel(db);
  const requireHub = (code: unknown, field: string) => {
    const hub = typeof code === 'string' ? hubs.get(code) : undefined;
    if (!hub || !hub.active) throw new ApiError('VALIDATION_ERROR', `${field} must be an existing active hub`);
    return hub.code;
  };
  const load = (id: string, auth: Auth) => {
    const s = shipments.get(id, auth.org_id);
    if (!s) throw new ApiError('NOT_FOUND', `Shipment ${id} not found`);
    return s;
  };
  return {
    create(body: any, auth: Auth): Shipment {
      const origin_hub = requireHub(body?.origin_hub, 'origin_hub');
      const dest_hub = requireHub(body?.dest_hub, 'dest_hub');
      if (origin_hub === dest_hub) throw new ApiError('VALIDATION_ERROR', 'origin_hub and dest_hub must be different');
      const weight_g = int(body.weight_g);
      if (weight_g === undefined || weight_g < 1 || weight_g > 500000) throw new ApiError('VALIDATION_ERROR', 'weight_g must be between 1 and 500000');
      const priority = int(body.priority);
      if (priority === undefined || ![1, 2, 3].includes(priority)) throw new ApiError('VALIDATION_ERROR', 'priority must be 1, 2, or 3');
      if (body.manifest_ref !== undefined && body.manifest_ref !== null && !(typeof body.manifest_ref === 'string' && MANIFEST.test(body.manifest_ref))) {
        throw new ApiError('VALIDATION_ERROR', 'manifest_ref must match /^MF-\\d{8}$/');
      }
      const now = Date.now();
      const shipment: Shipment = {
        id: newId(), org_id: auth.org_id, origin_hub, dest_hub, weight_g, priority, status: 'DRAFT',
        manifest_ref: body.manifest_ref ?? null, created_by: auth.user_id, created_at: now, updated_at: now,
      };
      shipments.insert(shipment);
      return shipment;
    },
    list(query: any, auth: Auth) {
      const num = (v: unknown, fallback: number) => (v === undefined ? fallback : Number(v));
      const offset = num(query.offset, 0);
      const limit = num(query.limit, 20);
      // Decision 3: out-of-range limit is rejected, never clamped.
      if (!Number.isInteger(limit) || limit < 1 || limit > 100) throw new ApiError('VALIDATION_ERROR', 'limit must be between 1 and 100');
      if (!Number.isInteger(offset) || offset < 0) throw new ApiError('VALIDATION_ERROR', 'offset must be a non-negative integer');
      const priority = query.priority === undefined ? undefined : Number(query.priority);
      if (priority !== undefined && ![1, 2, 3].includes(priority)) throw new ApiError('VALIDATION_ERROR', 'priority must be 1, 2, or 3');
      const { rows, total } = shipments.list({
        org_id: auth.org_id, offset, limit, priority,
        status: query.status, origin_hub: query.origin_hub, dest_hub: query.dest_hub,
      });
      return { rows, meta: { total, offset, limit } };
    },
    get(id: string, auth: Auth) {
      const s = load(id, auth);
      return { ...s, events: shipments.events(id) };
    },
    transition(id: string, body: any, auth: Auth) {
      const s = load(id, auth);
      const to = body?.to_status as Status;
      if (typeof to !== 'string') throw new ApiError('VALIDATION_ERROR', 'to_status is required');
      if (TERMINAL.includes(s.status)) throw new ApiError('TRANSITION_ERROR', `Shipment is in terminal state ${s.status}`);
      let rule = (TRANSITIONS[s.status] ?? []).find((r) => r.to === to);
      if (!rule && to === 'EXCEPTION') rule = { to: 'EXCEPTION', roles: ['admin'] };
      if (!rule) throw new ApiError('TRANSITION_ERROR', `Cannot transition from ${s.status} to ${to}`);
      if (!rule.roles.includes(auth.role)) throw new ApiError('AUTH_FORBIDDEN', 'Insufficient role for this operation');
      let manifest_ref: string | null = null;
      if (to === 'MANIFESTED') {
        const candidate = body.manifest_ref ?? s.manifest_ref;
        if (typeof candidate !== 'string' || !MANIFEST.test(candidate)) {
          throw new ApiError('VALIDATION_ERROR', 'manifest_ref is required for DRAFT to MANIFESTED transition and must match /^MF-\\d{8}$/');
        }
        manifest_ref = candidate;
      }
      if (to === 'EXCEPTION' && (typeof body.reason !== 'string' || !body.reason)) {
        throw new ApiError('VALIDATION_ERROR', 'reason is required when transitioning to EXCEPTION');
      }
      const event: ShipmentEvent = {
        id: newId(), shipment_id: id, from_status: s.status, to_status: to, changed_by: auth.user_id,
        changed_at: Date.now(), reason: typeof body.reason === 'string' ? body.reason : null,
      };
      shipments.transition(id, to, manifest_ref, event);
      return { ...load(id, auth), event };
    },
  };
};
