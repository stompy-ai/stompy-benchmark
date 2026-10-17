import { Router } from 'express';
import type { Db } from '../db.js';
import { requireRole } from '../middleware/auth.js';
import { shipmentService } from '../services/shipment.service.js';
import { ok } from '../utils/response.js';
export function shipmentRoutes(db: Db) {
  const service = shipmentService(db);
  const router = Router();
  const anyRole = requireRole('operator', 'dispatcher', 'admin');
  router.post('/', anyRole, (req, res) => ok(res, service.create(req.body, req.auth), 201));
  router.get('/', anyRole, (req, res) => {
    const { rows, meta } = service.list(req.query, req.auth);
    ok(res, rows, 200, meta);
  });
  router.get('/:id', anyRole, (req, res) => ok(res, service.get(String(req.params.id), req.auth)));
  // Role is checked per transition inside the service.
  router.patch('/:id/transition', anyRole, (req, res) => ok(res, service.transition(String(req.params.id), req.body, req.auth)));
  return router;
}
