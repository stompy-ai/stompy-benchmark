import { createHmac, timingSafeEqual } from 'node:crypto';
import type { NextFunction, Request, Response } from 'express';
import { ROLES, type Role } from '../types/index.js';
import { fail } from '../utils/response.js';

export function authenticate(req: Request, res: Response, next: NextFunction) {
  const raw = req.header('x-meridian-auth');
  if (!raw) return fail(res, 'AUTH_INVALID', 'Missing or malformed authentication token');
  const parts = Buffer.from(raw, 'base64').toString('utf8').split(':');
  if (parts.length !== 5) return fail(res, 'AUTH_INVALID', 'Missing or malformed authentication token');
  const [org_id, user_id, role, expiry, sig] = parts;
  const secret = process.env.MERIDIAN_AUTH_SECRET ?? '';
  const expected = createHmac('sha256', secret).update(`${org_id}:${user_id}:${role}:${expiry}`).digest('hex');
  const valid = sig.length === expected.length && timingSafeEqual(Buffer.from(sig), Buffer.from(expected));
  if (!valid || !ROLES.includes(role as Role) || !/^\d+$/.test(expiry)) {
    return fail(res, 'AUTH_INVALID', 'Missing or malformed authentication token');
  }
  if (Number(expiry) < Date.now()) return fail(res, 'AUTH_EXPIRED', 'Token has expired');
  req.auth = { org_id, user_id, role: role as Role };
  next();
}

export const requireRole = (...roles: Role[]) => (req: Request, res: Response, next: NextFunction) =>
  roles.includes(req.auth.role) ? next() : fail(res, 'AUTH_FORBIDDEN', 'Insufficient role for this operation');
