import Database from 'better-sqlite3';
export type Db = Database.Database;
export function openDb(path = ':memory:'): Db {
  const db = new Database(path);
  db.pragma('foreign_keys = ON');
  db.exec(`
    CREATE TABLE IF NOT EXISTS mrd_hubs (
      code TEXT PRIMARY KEY, name TEXT NOT NULL, lat REAL NOT NULL, lng REAL NOT NULL,
      active INTEGER NOT NULL DEFAULT 1, created_at INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS mrd_shipments (
      id TEXT PRIMARY KEY, org_id TEXT NOT NULL,
      origin_hub TEXT NOT NULL REFERENCES mrd_hubs(code), dest_hub TEXT NOT NULL REFERENCES mrd_hubs(code),
      weight_g INTEGER NOT NULL, priority INTEGER NOT NULL CHECK (priority IN (1, 2, 3)),
      status TEXT NOT NULL DEFAULT 'DRAFT', manifest_ref TEXT, created_by TEXT NOT NULL,
      created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS mrd_events (
      id TEXT PRIMARY KEY, shipment_id TEXT NOT NULL REFERENCES mrd_shipments(id),
      from_status TEXT NOT NULL, to_status TEXT NOT NULL, changed_by TEXT NOT NULL,
      changed_at INTEGER NOT NULL, reason TEXT);
    CREATE INDEX IF NOT EXISTS idx_events_shipment ON mrd_events(shipment_id);
  `);
  db.prepare(`INSERT OR IGNORE INTO mrd_hubs (code, name, lat, lng, active, created_at) VALUES
    ('LAX', 'Los Angeles Hub', 33.9425, -118.4081, 1, 1699000000000),
    ('JFK', 'New York JFK Hub', 40.6413, -73.7781, 1, 1699000000000),
    ('ORD', 'Chicago O''Hare Hub', 41.9742, -87.9073, 1, 1699000000000),
    ('DFW', 'Dallas Fort Worth Hub', 32.8998, -97.0403, 1, 1699000000000),
    ('MIA', 'Miami Hub', 25.7959, -80.2870, 1, 1699000000000)`).run();
  return db;
}
