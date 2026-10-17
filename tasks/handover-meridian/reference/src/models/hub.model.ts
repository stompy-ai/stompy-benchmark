import type { Db } from '../db.js';
import type { Hub } from '../types/index.js';
const row = (r: any): Hub => ({ ...r, active: r.active === 1 });
export const hubModel = (db: Db) => ({
  list: (active?: boolean): Hub[] =>
    (active === undefined
      ? db.prepare('SELECT * FROM mrd_hubs ORDER BY code').all()
      : db.prepare('SELECT * FROM mrd_hubs WHERE active = ? ORDER BY code').all(active ? 1 : 0)
    ).map(row),
  get: (code: string): Hub | undefined => {
    const r = db.prepare('SELECT * FROM mrd_hubs WHERE code = ?').get(code);
    return r ? row(r) : undefined;
  },
  insert: (hub: Hub) =>
    db.prepare('INSERT INTO mrd_hubs (code, name, lat, lng, active, created_at) VALUES (?, ?, ?, ?, ?, ?)')
      .run(hub.code, hub.name, hub.lat, hub.lng, hub.active ? 1 : 0, hub.created_at),
});
