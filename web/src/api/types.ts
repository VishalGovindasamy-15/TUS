export interface UserOut {
  id: string; phone: string; org_id: string | null; role: string;
  is_active: boolean; mfa_enabled: boolean;
}

export interface OrgOut {
  id: string; name: string; org_type: string; approval_status: string;
  rejection_reason: string | null; categories: string[];
  notif_channels: string[]; notif_language: string;
  webhook_secret: string | null; created_at: string;
}

export interface KycDoc {
  id: string; org_id: string; document_type: string; file_url: string;
  status: string; uploaded_at: string;
}

export interface Product { id: string; org_id: string; product_code: string; name: string; category: string; }
export interface Batch {
  id: string; product_id: string; org_id: string; batch_number: string;
  quantity: number; mfg_date: string | null; expiry_date: string | null;
  recalled: boolean; recall_reason: string | null; units_generated: number;
}
export interface Unit {
  id: string; batch_id: string; product_id: string; current_state: string;
  holder_org_id: string | null; verify_count: number;
  last_verified_at: string | null; created_at: string;
}

export interface CustodyEvent {
  id: string; client_event_id: string; target_type: string; target_id: string;
  event_type: string; actor_org_id: string | null; actor_user_id: string | null;
  gps_lat: number | null; gps_lng: number | null;
  resulting_state: string | null; created_at: string;
}

export interface AlertItem {
  id: string; org_id: string; target_type: string; target_id: string;
  reason: string; severity: string; status: string; detail: string | null;
  created_at: string;
}

export interface TreeNode { org_id: string; name: string; org_type: string }
export interface TreeEdge { from_org_id: string; to_org_id: string; product_code: string | null; authorized: boolean }
export interface NetworkTree { manufacturer_org_id: string | null; nodes: TreeNode[]; edges: TreeEdge[] }
export interface Invite {
  code: string; created_by_org_id: string; manufacturer_org_id: string;
  product_code: string | null; authorized: boolean;
  expires_at: string | null; used_by_org_id: string | null;
}

export interface SocialListing {
  id: string; org_id: string; platform: string; post_url: string; unit_ids: string[];
}

export interface ContainerChild { child_type: string; child_id: string; state: string | null }
export interface ContainerOut {
  id: string; container_type: string; holder_org_id: string | null;
  state: string; disaggregated: boolean; parent_container_id: string | null;
  children: ContainerChild[]; created_at: string;
}

export interface SessionOut {
  id: string; device_info: string | null; created_at: string;
  expires_at: string; revoked_at: string | null;
}

export interface RegulatorGrant {
  id: string; regulator_user_id: string; batch_id: string; reason: string;
  expires_at: string; revoked_at: string | null; created_at: string;
}

export interface FraudPatterns {
  top_flag_reasons: { reason: string; count: number }[];
  by_severity: { severity: string; count: number }[];
  by_day: { day: string; count: number }[];
}

export interface VerifyResult {
  status: 'genuine' | 'not_yet_in_circulation' | 'flagged' | 'recalled';
  unit_id: string; product_code: string | null; product_name: string | null;
  batch_number: string | null; flag_reason: string | null;
  disclosures: { field_key: string; label: string; value: string }[];
  last_events: { event_type: string; actor_org_id: string | null; timestamp: string; resulting_state: string | null }[];
}

export interface DisclosureField {
  id: string; category: string; field_key: string; label: string;
  field_type: string; required: boolean; display_order: number;
}
