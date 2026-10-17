import { Router } from 'express';
import type { Db } from '../db.js';
import { requireRole } from '../middleware/auth.js';
import { hubService } from '../services/hub.service.js';
import { ok } from '../utils/response.js';
export function hubRoutes(db: Db) {
  const service = hubService(db);
  const router = Router();
  router.get('/', requireRole('operator', 'dispatcher', 'admin'), (req, res) => {
    const active = req.query.active === undefined ? undefined : req.query.active === 'true';
    ok(res, service.list(active));
  });
  router.post('/', requireRole('admin'), (req, res) => ok(res, service.create(req.body), 201));
  return router;
}
