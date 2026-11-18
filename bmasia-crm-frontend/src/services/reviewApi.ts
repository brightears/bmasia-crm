/**
 * Change proposals ("suggestions") for the Review page: `/api/v1/change-proposals/`.
 *
 * Every decision sends the `seen_version` the proposal was shown with. Nothing here retries a
 * decision: a failed or unanswered decision is reported to the caller, which re-reads the proposal.
 * Errors are never logged with their request or response bodies.
 */
import { authApi } from './authService';

export type ProposalKind = 'field_update' | 'new_contact' | 'note' | 'task' | 'link' | 'other';
export type ProposalStatus = 'proposed' | 'accepted' | 'edited' | 'rejected' | 'expired' | 'superseded' | 'failed';
export type EvidenceState = 'verified_captured' | 'verified_agent_recorded' | 'unverified';
export type ProposerKind = 'agent' | 'ai' | 'job' | 'human';
export type PatchValue = string | null;

export interface ProposalHistoryEntry {
  action: string;
  by: string;
  at: string;
  note?: string;
}

export interface ProposalConflict {
  id: string;
  proposer_username: string;
  patch: Record<string, PatchValue>;
  evidence_occurred_at: string | null;
  created_at: string;
}

/** Present only once the backend sends it (feature-detected). */
export interface ProposalWarning {
  field?: string;
  code: string;
  detail?: string;
}

export interface ChangeProposal {
  id: string;
  seen_version: string;
  company_id: string;
  company_name: string;
  target_collection: 'company' | 'contact' | 'task';
  target_id: string;
  kind: ProposalKind;
  patch: Record<string, PatchValue>;
  applied_patch: Record<string, PatchValue> | null;
  current_values: Record<string, unknown>;
  expected_version: string;
  evidence: EvidenceState;
  evidence_quote: string;
  evidence_verified: boolean;
  evidence_source_system: string;
  evidence_source_ref: string;
  evidence_source_url: string;
  evidence_occurred_at: string | null;
  activity_id: string | null;
  evidence_recorded_by: string | null;
  evidence_recorded_via: string | null;
  evidence_recorder_is_agent: boolean;
  rationale: string;
  proposer_username: string;
  proposer_kind: ProposerKind;
  proposed_via: string;
  model: string;
  prompt_version: string;
  confidence: number | null;
  status: ProposalStatus;
  fingerprint: string;
  batch_key: string;
  reviewer_username: string;
  reviewed_at: string | null;
  decision_note: string;
  history: ProposalHistoryEntry[];
  conflicts_with: ProposalConflict[];
  target_changed_at: string | null;
  last_apply_error: string;
  applied_record_id: string;
  applied_audit_id: string | null;
  superseded_by_id: string | null;
  expires_at: string;
  created_at: string;
  updated_at: string;
  /** Later backend versions: per-field warnings such as `mixed_script`. */
  warnings?: ProposalWarning[];
  /** Later backend versions, in the answer to accepting a new contact: the contact created (inactive). */
  created_contact_id?: string;
  apply_note?: string;
  /** Later backend versions may flag mixed scripts directly. */
  mixed_script?: boolean | string[] | Record<string, unknown>;
}

/** The part of a proposal a 409 answer carries. */
export interface ProposalSnapshot {
  id: string;
  seen_version: string;
  status: ProposalStatus;
  patch: Record<string, PatchValue>;
  current_values: Record<string, unknown>;
  expected_version: string;
  target_changed_at: string | null;
}

export interface ReviewSettings {
  kinds: Record<string, Record<string, string[]>>;
  proposals_enabled: boolean;
  activity_writes_enabled: boolean;
  /** Later backend versions: whether the calling user may decide, and why not. */
  you_can_review?: boolean;
  review_refusal?: string | null;
  reviewing_configured?: boolean;
}

export interface Page<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface ProposalFilters {
  status?: ProposalStatus[];
  kind?: string[];
  company?: string;
  proposer?: string;
  page?: number;
  page_size?: number;
  ordering?: string;
}

export interface BulkRejectResult {
  rejected: string[];
  skipped: { id: string; status: string; code: string; seen_version?: string }[];
  not_found: string[];
}

/** A refused or failed API call, with the stable `code` the backend sends. */
export class ReviewApiError extends Error {
  status?: number;
  code?: string;
  detail: string;
  body: Record<string, any>;

  constructor(status: number | undefined, code: string | undefined, detail: string, body: Record<string, any> = {}) {
    super(detail);
    this.name = 'ReviewApiError';
    this.status = status;
    this.code = code;
    this.detail = detail;
    this.body = body;
  }

  /** The fresh snapshot sent with a 409 `stale_view` or `record_changed`. */
  get snapshot(): ProposalSnapshot | undefined {
    const p = this.body?.proposal;
    return p && typeof p === 'object' && typeof p.seen_version === 'string' ? (p as ProposalSnapshot) : undefined;
  }

  /** True when no answer came back: the decision may or may not have been stored. */
  get noAnswer(): boolean {
    return this.status === undefined;
  }
}

const toError = (error: any): ReviewApiError => {
  const response = error?.response;
  if (!response) {
    return new ReviewApiError(undefined, 'no_answer', 'No answer from the server.');
  }
  const data = response.data && typeof response.data === 'object' && !Array.isArray(response.data) ? response.data : {};
  const detail =
    typeof data.detail === 'string' && data.detail
      ? data.detail
      : `The server refused the request (${response.status}).`;
  return new ReviewApiError(response.status, typeof data.code === 'string' ? data.code : undefined, detail, data);
};

const call = async <T>(run: () => Promise<{ data: T }>): Promise<T> => {
  try {
    return (await run()).data;
  } catch (error) {
    throw toError(error);
  }
};

const BASE = '/change-proposals/';

const params = (filters: ProposalFilters) => {
  const search = new URLSearchParams();
  filters.status?.forEach((s) => search.append('status', s));
  filters.kind?.forEach((k) => search.append('kind', k));
  if (filters.company) search.set('company', filters.company);
  if (filters.proposer) search.set('proposer', filters.proposer);
  if (filters.page) search.set('page', String(filters.page));
  if (filters.page_size) search.set('page_size', String(filters.page_size));
  if (filters.ordering) search.set('ordering', filters.ordering);
  return search;
};

/** Open proposals are read 200 at a time; the reviewer loads more when more exist. */
export const OPEN_PAGE_SIZE = 200;

const reviewApi = {
  getSettings: (): Promise<ReviewSettings> => call(() => authApi.get<ReviewSettings>(`${BASE}allowlist/`)),

  list: (filters: ProposalFilters): Promise<Page<ChangeProposal>> =>
    call(() => authApi.get<Page<ChangeProposal>>(BASE, { params: params(filters) })),

  /** One page of open proposals: newest first, or soonest to expire first. */
  listOpen: (page: number, sort: 'newest' | 'expiring' = 'newest'): Promise<Page<ChangeProposal>> =>
    reviewApi.list({
      status: ['proposed'],
      page,
      page_size: OPEN_PAGE_SIZE,
      ordering: sort === 'expiring' ? 'expires_at' : '-created_at',
    }),

  openCount: async (company?: string): Promise<number> =>
    (await reviewApi.list({ status: ['proposed'], company, page_size: 1 })).count,

  get: (id: string): Promise<ChangeProposal> => call(() => authApi.get<ChangeProposal>(`${BASE}${id}/`)),

  accept: (id: string, seenVersion: string, note?: string): Promise<ChangeProposal> =>
    call(() =>
      authApi.post<ChangeProposal>(`${BASE}${id}/accept/`, { seen_version: seenVersion, ...(note ? { note } : {}) }),
    ),

  acceptWithEdits: (
    id: string,
    seenVersion: string,
    edits: Record<string, PatchValue>,
    dropFields: string[],
    note?: string,
  ): Promise<ChangeProposal> =>
    call(() =>
      authApi.post<ChangeProposal>(`${BASE}${id}/accept-with-edits/`, {
        seen_version: seenVersion,
        ...(Object.keys(edits).length ? { edits } : {}),
        ...(dropFields.length ? { drop_fields: dropFields } : {}),
        ...(note ? { note } : {}),
      }),
    ),

  reject: (id: string, seenVersion: string, reason: string): Promise<ChangeProposal> =>
    call(() => authApi.post<ChangeProposal>(`${BASE}${id}/reject/`, { seen_version: seenVersion, reason })),

  reopen: (id: string, seenVersion: string, note: string): Promise<ChangeProposal> =>
    call(() => authApi.post<ChangeProposal>(`${BASE}${id}/reopen/`, { seen_version: seenVersion, note })),

  bulkReject: (items: { id: string; seen_version: string }[], reason: string): Promise<BulkRejectResult> =>
    call(() => authApi.post<BulkRejectResult>(`${BASE}bulk-reject/`, { items, reason })),

  /** Name and role flags of a contact a proposal targets (for the record label and warnings). */
  getContact: (id: string): Promise<Record<string, any>> =>
    call(() => authApi.get(`/contacts/${encodeURIComponent(id)}/`)),
};

export default reviewApi;
