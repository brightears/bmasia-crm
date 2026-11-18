/**
 * What the page says after a decision or a refusal. One line each, plain words.
 * Server details are passed through as plain text, never as markup.
 */
import type { ChangeProposal, ProposalSnapshot } from '../../services/reviewApi';
import { ReviewApiError } from '../../services/reviewApi';
import { displayValue, fieldLabel } from './reviewModel';
import type { CardNotice, DecisionResult } from './ProposalCard';

const short = (value: string, max = 60) => (value.length > max ? `${value.slice(0, max)}…` : value);

const fieldsSummary = (patch: Record<string, unknown> | null | undefined, max = 2): string => {
  const entries = Object.entries(patch || {});
  const parts = entries.slice(0, max).map(([k, v]) => `${fieldLabel(k)} “${short(displayValue(v) || 'empty')}”`);
  const more = entries.length > max ? ` and ${entries.length - max} more` : '';
  return parts.join(', ') + more;
};

export const acceptedText = (p: ChangeProposal): string => {
  const applied = p.applied_patch || p.patch;
  const how = p.status === 'edited' ? 'Accepted with your edits' : 'Accepted';
  switch (p.kind) {
    case 'new_contact':
      return `${how}: contact “${short(displayValue(applied?.name))}” created at ${p.company_name}.`;
    case 'task':
      return `${how}: task “${short(displayValue(applied?.title))}” created for ${p.company_name}.`;
    case 'note':
      return `${how}: text added to the notes (${p.target_collection === 'contact' ? 'contact' : 'company'}, ${p.company_name}).`;
    default:
      return `${how}: ${fieldsSummary(applied)} saved for ${p.company_name}.`;
  }
};

export const rejectedText = (reason: string) => `Rejected. Reason: ${short(reason, 120)}`;

/** A result for a proposal that turned out to be closed already. */
export const closedResult = (p: ChangeProposal): DecisionResult | null => {
  switch (p.status) {
    case 'accepted':
    case 'edited':
      return {
        tone: 'info',
        text: `Already accepted${p.reviewer_username ? ` by ${p.reviewer_username}` : ''}. Nothing more was done.`,
      };
    case 'rejected':
      return {
        tone: 'info',
        text: `Already rejected${p.reviewer_username ? ` by ${p.reviewer_username}` : ''}. Nothing more was done.`,
      };
    case 'expired':
      return { tone: 'warning', text: 'This suggestion expired. Nothing was applied.' };
    case 'superseded':
      return {
        tone: 'info',
        text: 'No change needed: the record already has this value, or a newer suggestion replaced it.',
      };
    case 'failed':
      return { tone: 'error', text: `Could not be applied${p.last_apply_error ? `: ${p.last_apply_error}` : '.'}` };
    default:
      return null;
  }
};

/** In one line, what differs between what was shown and the fresh snapshot. */
export const whatChanged = (before: ChangeProposal, after: ProposalSnapshot | ChangeProposal): string => {
  if (before.status !== after.status) return `its status is now “${after.status}”`;
  const keys = Object.keys({ ...(before.current_values || {}), ...(after.current_values || {}) });
  const changed = keys.filter(
    (k) => displayValue(before.current_values?.[k]) !== displayValue(after.current_values?.[k]),
  );
  if (changed.length)
    return `the current ${changed.map(fieldLabel).join(', ')} ${changed.length === 1 ? 'was' : 'were'} re-read`;
  if (JSON.stringify(before.patch) !== JSON.stringify(after.patch)) return 'the suggested values changed';
  if ((before.target_changed_at || '') !== (after.target_changed_at || '')) return 'the record was marked as changed';
  return 'its details were updated';
};

const errorList = (body: Record<string, any>): string[] => {
  const errors = body?.errors;
  if (!errors || typeof errors !== 'object') return [];
  return Object.entries(errors).map(([field, messages]) => {
    const text = Array.isArray(messages) ? messages.map(String).join(' ') : String(messages);
    return `${fieldLabel(field)}: ${text}`;
  });
};

export type ErrorOutcome =
  | { kind: 'notice'; notice: CardNotice; refresh: boolean; snapshot?: ProposalSnapshot }
  | { kind: 'page_read_only'; reason: string }
  | { kind: 'card_read_only'; reason: string }
  | { kind: 'switched_off' };

/**
 * What a refused decision means for the card. Never a retry: at most the proposal is read again,
 * and the reviewer decides again with a fresh click.
 */
export const outcomeOf = (p: ChangeProposal, error: ReviewApiError): ErrorOutcome => {
  const detail = error.detail;
  if (error.noAnswer) {
    return {
      kind: 'notice',
      refresh: true,
      notice: {
        tone: 'error',
        text: 'No answer from the server, so the decision may or may not have been saved. The suggestion was read again; check it before deciding.',
      },
    };
  }
  if (error.status === 409) {
    const snap = error.snapshot;
    switch (error.code) {
      case 'stale_view':
        return {
          kind: 'notice',
          refresh: true,
          snapshot: snap,
          notice: {
            tone: 'warning',
            text: `Nothing was done: this suggestion changed since it was loaded (${snap ? whatChanged(p, snap) : 'it was updated'}). Look at it again and decide.`,
          },
        };
      case 'record_changed':
        return {
          kind: 'notice',
          refresh: true,
          snapshot: snap,
          notice: {
            tone: 'warning',
            text: 'Nothing was applied: the record changed after this was suggested. The current values were just re-read; compare them and decide again.',
          },
        };
      case 'not_open':
      case 'not_rejected':
        return { kind: 'notice', refresh: true, notice: { tone: 'info', text: `Nothing was done: ${detail}` } };
      case 'expired':
        return {
          kind: 'notice',
          refresh: true,
          notice: { tone: 'warning', text: 'This suggestion expired. Nothing was applied.' },
        };
      default:
        return { kind: 'notice', refresh: true, notice: { tone: 'error', text: detail } };
    }
  }
  if (error.status === 403) {
    if (error.code === 'not_enabled') return { kind: 'switched_off' };
    if (error.code === 'human_review_required') return { kind: 'page_read_only', reason: detail };
    if (error.code === 'reviewer_is_party') return { kind: 'card_read_only', reason: detail };
    return { kind: 'notice', refresh: false, notice: { tone: 'error', text: detail } };
  }
  if (error.status === 422) {
    const isApply = error.code === 'apply_refused';
    return {
      kind: 'notice',
      refresh: true,
      notice: {
        tone: 'error',
        text: isApply
          ? `The record refused the change and nothing was applied: ${detail}`
          : `Nothing was applied: ${detail}`,
        details: errorList(error.body),
      },
    };
  }
  if (error.status === 404) {
    return { kind: 'notice', refresh: false, notice: { tone: 'error', text: 'This suggestion no longer exists.' } };
  }
  return {
    kind: 'notice',
    refresh: error.status !== undefined && error.status >= 500,
    notice: { tone: 'error', text: detail },
  };
};

/** Field errors from a 422 `invalid_value`, for the edit form. */
export const fieldErrorsOf = (error: ReviewApiError): Record<string, string> => {
  const errors = error.body?.errors;
  if (!errors || typeof errors !== 'object') return {};
  return Object.fromEntries(
    Object.entries(errors).map(([k, v]) => [k, Array.isArray(v) ? v.map(String).join(' ') : String(v)]),
  );
};
