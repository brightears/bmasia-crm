import { authApi } from './authService';

/**
 * The Renewals page API (GET /api/v1/renewals/). Read-only.
 * The renewal state of each row is decided on the server (renewals_page_service.py);
 * the page only shows it.
 */

export type RenewalStateKey =
  | 'not_started'
  | 'drafted'
  | 'sent'
  | 'signed'
  | 'invoiced'
  | 'paid'
  | 'renewed_unlinked'
  | 'auto_renews'
  | 'lapsed'
  | 'lost';

export type RenewalGroup = 'open' | 'renewed' | 'auto' | 'lost';

export type AttentionKey =
  | 'ended_nothing_sent'
  | 'ended_not_signed'
  | 'ending_soon_nothing_sent'
  | 'renewed_unlinked';

export type EntityKey = 'th' | 'hk';

export interface RenewalSuccessor {
  contract_id: string;
  contract_number: string;
  status: string;
  start_date: string | null;
  end_date: string | null;
  term_months: number | null;
  value: number;
  currency: string;
  signed_date: string | null;
  sent_date: string | null;
  invoice_state: 'none' | 'invoiced' | 'paid';
  other_company: boolean;
}

export interface RenewalRow {
  // The Renewal Book row for the term (same fields as /contracts/renewal-book/).
  contract_id: string;
  company_id: string;
  contract_number: string;
  corporate_group: string;
  company: string;
  country: string;
  end_date: string;
  zones: number;
  zones_source: 'service_locations' | 'contracted_zone_count';
  value: number;
  currency: string;
  product: 'Soundtrack' | 'Beat Breeze' | 'Other' | string;
  lifecycle_type: string;
  status: string;
  auto_renew: boolean;
  billing_frequency: string;
  // Added for the page.
  property_name: string;
  contract_type: string;
  start_date: string | null;
  term_months: number | null;
  entity: EntityKey | null;
  owner: string | null;
  owner_source: 'opportunity_owner' | 'bmasia_contact' | null;
  days_from_end: number | null;
  renewal: {
    state: RenewalStateKey;
    label: string;
    group: RenewalGroup;
    reason: string;
    attention: AttentionKey | null;
    attention_label: string | null;
    successor: RenewalSuccessor | null;
    other_linked: { contract_id: string; contract_number: string; status: string; lifecycle_type: string }[];
    value_change: number | null;
    value_change_basis: 'term' | 'per_year' | null;
  };
}

export interface RenewalMonth {
  year: number;
  month: number;
  label: string;
  count: number;
  attention: number;
  open: number;
  renewed: number;
  auto: number;
  lost: number;
}

export interface RenewalsResponse {
  as_of: string;
  view: 'month' | 'open';
  year: number;
  month: number | null;
  month_label: string | null;
  entity: '' | EntityKey;
  window: { start: string; end: string };
  states: { key: RenewalStateKey; label: string; group: RenewalGroup }[];
  attention_reasons: { key: AttentionKey; label: string }[];
  months: RenewalMonth[];
  count: number;
  rows: RenewalRow[];
}

export interface RenewalsQuery {
  view: 'month' | 'open';
  year: number;
  month?: number;
  entity?: '' | EntityKey;
}

export async function getRenewals(query: RenewalsQuery): Promise<RenewalsResponse> {
  const params: Record<string, string | number> = { year: query.year };
  if (query.view === 'open') params.view = 'open';
  else if (query.month) params.month = query.month;
  if (query.entity) params.entity = query.entity;
  const response = await authApi.get<RenewalsResponse>('/renewals/', { params });
  return response.data;
}
