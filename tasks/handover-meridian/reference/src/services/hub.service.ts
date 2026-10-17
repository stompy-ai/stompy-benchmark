import type { Db } from '../db.js';
import { hubModel } from '../models/hub.model.js';
import type { Hub } from '../types/index.js';
import { ApiError } from '../utils/response.js';
export const hubService = (db: Db) => {
  const hubs = hubModel(db);
  return {
    list: (active?: boolean) => hubs.list(active),
    create(body: any): Hub {
      if (typeof body?.code !== 'string' || !/^[A-Z0-9]{2,10}$/.test(body.code)) throw new ApiError('VALIDATION_ERROR', 'code must be 2-10 uppercase alphanumeric characters');
      if (typeof body.name !== 'string' || body.name.length < 1 || body.name.length > 200) throw new ApiError('VALIDATION_ERROR', 'name must be 1-200 characters');
      if (typeof body.lat !== 'number' || body.lat < -90 || body.lat > 90) throw new ApiError('VALIDATION_ERROR', 'lat must be between -90 and 90');
      if (typeof body.lng !== 'number' || body.lng < -180 || body.lng > 180) throw new ApiError('VALIDATION_ERROR', 'lng must be between -180 and 180');
      if (body.active !== undefined && typeof body.active !== 'boolean') throw new ApiError('VALIDATION_ERROR', 'active must be a boolean');
      if (hubs.get(body.code)) throw new ApiError('VALIDATION_ERROR', `Hub with code ${body.code} already exists`);
      const hub: Hub = { code: body.code, name: body.name, lat: body.lat, lng: body.lng, active: body.active ?? true, created_at: Date.now() };
      hubs.insert(hub);
      return hub;
    },
  };
};
