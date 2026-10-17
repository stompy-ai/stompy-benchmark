import type { Db } from '../db.js';
import type { Shipment, ShipmentEvent, Status } from '../types/index.js';

export interface ListFilter {
  org_id: string; offset: number; limit: number;
  status?: string; origin_hub?: string; dest_hub?: string; priority?: number;
}

export const shipmentModel = (db: Db) => ({
  insert: (s: Shipment) =>
    db.prepare(`INSERT INTO mrd_shipments (id, org_id, origin_hub, dest_hub, weight_g, priority, status, manifest_ref, created_by, created_at, updated_at)
      VALUES (@id, @org_id, @origin_hub, @dest_hub, @weight_g, @priority, @status, @manifest_ref, @created_by, @created_at, @updated_at)`).run(s),
  get: (id: string, org_id: string): Shipment | undefined =>
    db.prepare('SELECT * FROM mrd_shipments WHERE id = ? AND org_id = ?').get(id, org_id) as Shipment | undefined,
  list(f: ListFilter): { rows: Shipment[]; total: number } {
    const where: string[] = ['org_id = @org_id'];
    for (const k of ['status', 'origin_hub', 'dest_hub', 'priority'] as const) {
      if (f[k] !== undefined) where.push(`${k} = @${k}`);
    }
    const clause = `FROM mrd_shipments WHERE ${where.join(' AND ')}`;
    const total = (db.prepare(`SELECT COUNT(*) AS n ${clause}`).get(f) as { n: number }).n;
    const rows = db.prepare(`SELECT * ${clause} ORDER BY created_at DESC, id LIMIT @limit OFFSET @offset`).all(f) as Shipment[];
    return { rows, total };
  },
  // Decision 1: events are returned newest first.
  events: (shipment_id: string): ShipmentEvent[] =>
    db.prepare('SELECT * FROM mrd_events WHERE shipment_id = ? ORDER BY changed_at DESC, rowid DESC').all(shipment_id) as ShipmentEvent[],
  transition(id: string, to: Status, manifest_ref: string | null, event: ShipmentEvent) {
    db.transaction(() => {
      db.prepare('UPDATE mrd_shipments SET status = ?, manifest_ref = COALESCE(?, manifest_ref), updated_at = ? WHERE id = ?')
        .run(to, manifest_ref, event.changed_at, id);
      db.prepare(`INSERT INTO mrd_events (id, shipment_id, from_status, to_status, changed_by, changed_at, reason)
        VALUES (@id, @shipment_id, @from_status, @to_status, @changed_by, @changed_at, @reason)`).run(event);
    })();
  },
});
