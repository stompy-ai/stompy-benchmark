import express, { type NextFunction, type Request, type Response } from 'express';
import { openDb } from './db.js';
import { authenticate } from './middleware/auth.js';
import { hubRoutes } from './routes/hub.routes.js';
import { shipmentRoutes } from './routes/shipment.routes.js';
import { ApiError, fail } from './utils/response.js';

export function createApp(dbPath = ':memory:') {
  const db = openDb(dbPath);
  const app = express();
  app.use(express.json());
  app.use('/api/v1', authenticate);
  app.use('/api/v1/hubs', hubRoutes(db));
  app.use('/api/v1/shipments', shipmentRoutes(db));
  app.use((_req: Request, res: Response) => fail(res, 'NOT_FOUND', 'Route not found'));
  app.use((err: unknown, _req: Request, res: Response, _next: NextFunction) => {
    if (err instanceof ApiError) return fail(res, err.code, err.message);
    if (err && typeof err === 'object' && (err as any).type === 'entity.parse.failed') return fail(res, 'VALIDATION_ERROR', 'Malformed JSON body');
    fail(res, 'INTERNAL_ERROR', 'Unexpected server error');
  });
  return app;
}
