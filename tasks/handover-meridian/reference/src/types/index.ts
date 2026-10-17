export type Role = 'operator' | 'dispatcher' | 'admin';
export const ROLES: Role[] = ['operator', 'dispatcher', 'admin'];
export type Status =
  | 'DRAFT' | 'MANIFESTED' | 'IN_TRANSIT' | 'AT_HUB' | 'OUT_FOR_DELIVERY' | 'DELIVERED' | 'EXCEPTION' | 'RETURNED';
export interface Auth { org_id: string; user_id: string; role: Role }
export interface Hub { code: string; name: string; lat: number; lng: number; active: boolean; created_at: number }
export interface Shipment {
  id: string; org_id: string; origin_hub: string; dest_hub: string; weight_g: number; priority: number;
  status: Status; manifest_ref: string | null; created_by: string; created_at: number; updated_at: number;
}
export interface ShipmentEvent {
  id: string; shipment_id: string; from_status: Status; to_status: Status; changed_by: string;
  changed_at: number; reason: string | null;
}
declare global { namespace Express { interface Request { auth: Auth } } }
