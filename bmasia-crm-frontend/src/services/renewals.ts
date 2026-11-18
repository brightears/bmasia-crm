import { authApi } from './authService';

/**
 * The Renewals page API (GET /api/v1/renewals/). Read-only.
 * The renewal state of each row, the total it counts in and whether it counts in the
 * renewal rate are decided on the server (renewals_page_service.py); the page only shows them.
 */

export type RenewalStateKey =
  | 'not_started'
  | 'auto_unconfirmed'
  | 'drafted'
  | 'sent'
  | 'signed'
  | 'invoiced'
  | 'part_paid'
  | 'paid'
  | 'renewed_unlinked'
  | 'auto_renews'
  | 'lapsed'
  | 'lost'
  | 'placeholder';

export type RenewalGroup = 'open' | 'renewed' | 'auto' | 'lost' | 'excluded';

export type AttentionKey =
  | 'renewed_unlinked'
  | 'invoice_refunded'
  | 'auto_renew_ended'
  | 'ended_nothing_sent'
  | 'ended_not_signed'
  | 'ending_soon_nothing_sent';

export type EntityKey = 'th' | 'hk';
export type MonthBasis = 'funnel' | 'calendar';
export type LinkKind = 'renewal' | 'addon' | 'mid_term' | 'late';

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
  invoice_state: 'none' | 'invoiced' | 'part_paid' | 'paid';
  other_company: boolean;
}

export interface RenewalRow {
  // The Renewal Book row for the term (same fields as /contracts/renewal-book/, except the
  // book's own view of the renewal, which is under `book` and is not shown as the renewal).
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
  book: {
    successor_contract: string | null;
    successor_status: string | null;
    invoices_paid: boolean;
    outstanding_amount: number;
  };
  // Added for the page.
  /** The book's product, or where it says 'Other', the contract's service-location platforms. */
  product_display: string;
  product_source: 'renewal_book' | 'service_locations';
  property_name: string;
  contract_type: string;
  start_date: string | null;
  term_months: number | null;
  entity: EntityKey | null;
  owner: string | null;
  owner_source: 'opportunity_owner' | 'bmasia_contact' | null;
  /** Today minus the end date: positive once the term has ended. */
  days_from_end: number | null;
  /** An add-on: lifecycle type 'addon', or it starts well inside the term it is linked to. */
  is_addon: boolean;
  /** The term is still in status Sent: it was never activated. */
  never_activated: boolean;
  renewal: {
    state: RenewalStateKey;
    label: string;
    group: RenewalGroup;
    summary_bucket: RenewalGroup;
    in_rate: boolean;
    reason: string;
    attention: AttentionKey | null;
    attention_label: string | null;
    successor: RenewalSuccessor | null;
    other_linked: {
      contract_id: string;
      contract_number: string;
      status: string;
      lifecycle_type: string;
      link: LinkKind;
      link_label: string;
    }[];
    value_change: number | null;
    value_change_basis: 'term' | 'different_length' | null;
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
  placeholders: number;
}

export interface RenewalsResponse {
  as_of: string;
  view: 'month' | 'open';
  basis: MonthBasis;
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
  basis?: MonthBasis;
}

export async function getRenewals(query: RenewalsQuery): Promise<RenewalsResponse> {
  const params: Record<string, string | number> = { year: query.year };
  if (query.view === 'open') params.view = 'open';
  else if (query.month) params.month = query.month;
  if (query.entity) params.entity = query.entity;
  if (query.basis === 'calendar') params.basis = 'calendar';
  const response = await authApi.get<RenewalsResponse>('/renewals/', { params });
  return response.data;
}
