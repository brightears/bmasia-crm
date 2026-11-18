/** Invented proposals for the Review page tests. */
import type { ChangeProposal, ReviewSettings } from '../../services/reviewApi';

let n = 0;

export const makeProposal = (overrides: Partial<ChangeProposal> = {}): ChangeProposal => {
  n += 1;
  return {
    id: `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`,
    seen_version: `seen-${n}`,
    company_id: 'c0000000-0000-4000-8000-000000000001',
    company_name: 'Example Lagoon Hotel',
    target_collection: 'company',
    target_id: 'c0000000-0000-4000-8000-000000000001',
    kind: 'field_update',
    patch: { phone: '+66 2 111 2222' },
    applied_patch: null,
    current_values: { phone: '+66 2 000 0000' },
    expected_version: '2026-11-18T00:00:00Z',
    evidence: 'verified_captured',
    evidence_quote: 'our new number is +66 2 111 2222',
    evidence_verified: true,
    evidence_source_system: 'gmail',
    evidence_source_ref: 'msg-1@mail.example.com',
    evidence_source_url: '',
    evidence_occurred_at: '2026-11-17T09:00:00Z',
    activity_id: 'a0000000-0000-4000-8000-000000000001',
    evidence_recorded_by: 'capture.job',
    evidence_recorded_via: 'job',
    evidence_recorder_is_agent: false,
    rationale: '',
    proposer_username: 'example-agent',
    proposer_kind: 'agent',
    proposed_via: 'mcp',
    model: '',
    prompt_version: '',
    confidence: null,
    status: 'proposed',
    fingerprint: `fp-${n}`,
    batch_key: '',
    reviewer_username: '',
    reviewed_at: null,
    decision_note: '',
    history: [],
    conflicts_with: [],
    target_changed_at: null,
    last_apply_error: '',
    applied_record_id: '',
    applied_audit_id: null,
    superseded_by_id: null,
    expires_at: '2099-01-01T00:00:00Z',
    created_at: '2026-11-17T10:00:00Z',
    updated_at: '2026-11-17T10:00:00Z',
    ...overrides,
  };
};

export const settingsOn: ReviewSettings = {
  kinds: {
    field_update: {
      company: [
        'address_line1',
        'address_line2',
        'city',
        'country',
        'email',
        'phone',
        'postal_code',
        'state',
        'website',
      ],
      contact: ['department', 'email', 'linkedin_url', 'mobile', 'name', 'phone', 'preferred_contact_method', 'title'],
    },
    note: { company: ['notes'], contact: ['notes'] },
    new_contact: {
      contact: [
        'department',
        'email',
        'linkedin_url',
        'mobile',
        'name',
        'notes',
        'phone',
        'preferred_contact_method',
        'title',
      ],
    },
    task: {
      task: [
        'description',
        'due_date',
        'priority',
        'related_contact',
        'related_contract',
        'related_opportunity',
        'task_type',
        'title',
      ],
    },
  },
  proposals_enabled: true,
  activity_writes_enabled: true,
};
