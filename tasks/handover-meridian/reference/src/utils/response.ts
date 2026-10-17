import type { Response } from 'express';
export type ErrorCode =
  | 'VALIDATION_ERROR' | 'AUTH_INVALID' | 'AUTH_EXPIRED' | 'AUTH_FORBIDDEN' | 'NOT_FOUND' | 'TRANSITION_ERROR' | 'INTERNAL_ERROR';
const STATUS: Record<ErrorCode, number> = {
  VALIDATION_ERROR: 400, AUTH_INVALID: 401, AUTH_EXPIRED: 401, AUTH_FORBIDDEN: 403,
  NOT_FOUND: 404, TRANSITION_ERROR: 409, INTERNAL_ERROR: 500,
};
export class ApiError extends Error {
  constructor(public code: ErrorCode, message: string) { super(message); }
}
export function ok(res: Response, data: unknown, status = 200, meta?: object) {
  res.status(status).json({ ok: true, ts: Date.now(), data, ...(meta ? { meta } : {}) });
}
export function fail(res: Response, code: ErrorCode, message: string) {
  res.status(STATUS[code]).json({ ok: false, ts: Date.now(), error: { code, message } });
}
