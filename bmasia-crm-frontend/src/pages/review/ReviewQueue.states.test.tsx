/* eslint-disable testing-library/no-node-access, testing-library/prefer-screen-queries -- these tests query inside
   one card on purpose (several cards show the same buttons), and read data attributes and focus on cards. */
import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ReviewQueue from './ReviewQueue';
import ChangePreview from './ChangePreview';
import reviewApi, { ChangeProposal, ReviewApiError } from '../../services/reviewApi';
import { makeProposal, settingsOn } from './testFixtures';
import { resetReviewSettingsCache } from './useReviewStatus';
import { INACTIVE_TICK_LABEL } from './reviewModel';

jest.mock('../../services/authService', () => ({ __esModule: true, default: {}, authApi: {} }));
jest.mock('../../contexts/AuthContext', () => ({ useAuth: () => ({ user: { username: 'reviewer.one' } }) }));
jest.mock('../../services/reviewApi', () => {
  const actual = jest.requireActual('../../services/reviewApi');
  return {
    __esModule: true,
    ...actual,
    default: {
      getSettings: jest.fn(),
      listOpen: jest.fn(),
      list: jest.fn(),
      get: jest.fn(),
      accept: jest.fn(),
      acceptWithEdits: jest.fn(),
      reject: jest.fn(),
      getContact: jest.fn(),
    },
  };
});

const api = reviewApi as jest.Mocked<typeof reviewApi>;
const page = (rows: ChangeProposal[], count = rows.length, summary?: any) => ({
  count,
  next: null,
  previous: null,
  results: rows,
  ...(summary ? { summary } : {}),
});

const REASONS = {
  inactive: 'This contact is inactive. Activate it first to accept this suggestion.',
  moved: 'This contact now belongs to another company.',
  missing: 'This record no longer exists.',
  duplicate: 'A contact with this email or name already exists at the company.',
};

/** A company field update (no contact look-up, captured evidence: no other tick needed). */
const withState = (state: keyof typeof REASONS | 'present', extra: Partial<ChangeProposal> = {}) =>
  makeProposal({
    seen_version: `v-${state}`,
    patch: { city: 'Krabi' },
    current_values: { city: 'Trang' },
    target_state: state,
    target_state_reason: state === 'present' ? '' : REASONS[state],
    watched_fields: ['city'],
    ...extra,
  });

const duplicateContact = () =>
  makeProposal({
    seen_version: 'v-dup',
    kind: 'new_contact',
    target_collection: 'contact',
    target_id: '',
    evidence: 'verified_captured',
    patch: { name: 'Dana Example', email: 'dana@example.com' },
    current_values: {},
    target_state: 'duplicate',
    target_state_reason: REASONS.duplicate,
    watched_fields: ['email', 'name'],
  });

const renderPage = (entry = '/review') =>
  render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/review" element={<ReviewQueue />} />
      </Routes>
    </MemoryRouter>,
  );

const cardEl = (p: ChangeProposal) => document.querySelector(`[data-proposal-id="${p.id}"]`) as HTMLElement;
const findCard = async (p: ChangeProposal) => {
  await waitFor(() => expect(cardEl(p)).not.toBeNull());
  return within(cardEl(p));
};
const key = (k: string) => fireEvent.keyDown(window, { key: k });
const focusAndArm = async (p: ChangeProposal) => {
  await findCard(p);
  act(() => cardEl(p).focus());
  await act(() => new Promise((resolve) => setTimeout(resolve, 1700)));
};

beforeEach(() => {
  jest.resetAllMocks();
  resetReviewSettingsCache();
  api.getSettings.mockResolvedValue({ ...settingsOn, you_can_review: true });
  api.list.mockResolvedValue(page([]));
  api.getContact.mockResolvedValue({ name: 'Pat Example', is_primary: false });
});

const show = (rows: ChangeProposal[], count = rows.length) => api.listOpen.mockResolvedValue(page(rows, count));

describe.each(['missing', 'moved'] as const)('a %s target', (state) => {
  it('shows the reason at the top, blocks every accepting route with it, and keeps Reject', async () => {
    const p = withState(state);
    show([p]);
    renderPage('/review?tab=look');
    const card = await findCard(p);
    expect(card.getByTestId('target-state')).toHaveTextContent(REASONS[state]);
    expect(card.getByTestId('target-state').querySelector('bdi')).not.toBeNull();
    expect(card.getByRole('button', { name: 'Accept' })).toBeDisabled();
    expect(card.getByRole('button', { name: 'Edit' })).toBeDisabled();
    expect(card.getByRole('button', { name: 'Reject' })).toBeEnabled();
    expect(card.getByTestId('accept-blocked-reason')).toHaveTextContent(REASONS[state]);
    expect(card.queryByTestId('record-changed')).not.toBeInTheDocument();
    await focusAndArm(p);
    key('a');
    key('e');
    expect(api.accept).not.toHaveBeenCalled();
    expect(card.queryByLabelText('City')).not.toBeInTheDocument();
  });
});

describe('a duplicate new contact', () => {
  it('blocks plain Accept with the reason but lets the reviewer edit and accept the edited values', async () => {
    const p = duplicateContact();
    show([p]);
    api.acceptWithEdits.mockResolvedValue({
      ...p,
      status: 'edited',
      applied_patch: { name: 'Dana Other', email: 'dana.other@example.com' },
    });
    renderPage('/review?tab=look');
    const card = await findCard(p);
    expect(card.getByTestId('target-state')).toHaveTextContent(REASONS.duplicate);
    expect(card.getByRole('button', { name: 'Accept' })).toBeDisabled();
    expect(card.getByTestId('accept-blocked-reason')).toHaveTextContent(REASONS.duplicate);
    await focusAndArm(p);
    key('a');
    expect(api.accept).not.toHaveBeenCalled();
    fireEvent.click(card.getByRole('button', { name: 'Edit' }));
    fireEvent.change(card.getByLabelText('Email'), { target: { value: 'dana.other@example.com' } });
    fireEvent.click(card.getByRole('button', { name: 'Accept with edits' }));
    await waitFor(() =>
      expect(api.acceptWithEdits).toHaveBeenCalledWith(p.id, 'v-dup', { email: 'dana.other@example.com' }, []),
    );
  });
});

describe('an inactive target', () => {
  it('needs its own tick, then sends acknowledge_inactive with Accept', async () => {
    const p = withState('inactive');
    show([p]);
    api.accept.mockResolvedValue({ ...p, status: 'accepted', applied_patch: p.patch });
    renderPage('/review?tab=look');
    const card = await findCard(p);
    expect(card.getByTestId('target-state')).toHaveTextContent(REASONS.inactive);
    expect(card.getByRole('button', { name: 'Accept' })).toBeDisabled();
    expect(card.getByTestId('accept-blocked-reason')).toHaveTextContent(INACTIVE_TICK_LABEL);
    expect(card.getByRole('button', { name: 'Edit' })).toBeEnabled();
    fireEvent.click(card.getByLabelText(INACTIVE_TICK_LABEL));
    fireEvent.click(card.getByRole('button', { name: 'Accept' }));
    await waitFor(() => expect(api.accept).toHaveBeenCalledWith(p.id, 'v-inactive', { acknowledgeInactive: true }));
  });

  it('accept with edits waits for the tick too, then sends the acknowledgement', async () => {
    const p = withState('inactive');
    show([p]);
    api.acceptWithEdits.mockResolvedValue({ ...p, status: 'edited', applied_patch: { city: 'Krabi Town' } });
    renderPage('/review?tab=look');
    const card = await findCard(p);
    fireEvent.click(card.getByRole('button', { name: 'Edit' }));
    fireEvent.change(card.getByLabelText('City'), { target: { value: 'Krabi Town' } });
    expect(card.getByRole('button', { name: 'Accept with edits' })).toBeDisabled();
    expect(card.getByTestId('edit-blocked-reason')).toHaveTextContent(INACTIVE_TICK_LABEL);
    fireEvent.click(card.getByLabelText(INACTIVE_TICK_LABEL));
    fireEvent.click(card.getByRole('button', { name: 'Accept with edits' }));
    await waitFor(() =>
      expect(api.acceptWithEdits).toHaveBeenCalledWith(p.id, 'v-inactive', { city: 'Krabi Town' }, [], {
        acknowledgeInactive: true,
      }),
    );
  });

  it('the a key respects the tick', async () => {
    const p = withState('inactive');
    show([p]);
    api.accept.mockResolvedValue({ ...p, status: 'accepted', applied_patch: p.patch });
    renderPage('/review?tab=look');
    await focusAndArm(p);
    key('a');
    expect(api.accept).not.toHaveBeenCalled();
    fireEvent.click(within(cardEl(p)).getByLabelText(INACTIVE_TICK_LABEL));
    act(() => cardEl(p).focus());
    await act(() => new Promise((resolve) => setTimeout(resolve, 1700)));
    key('a');
    await waitFor(() => expect(api.accept).toHaveBeenCalledWith(p.id, 'v-inactive', { acknowledgeInactive: true }));
  });

  it('the tick belongs to the version shown and resets when the card changes', async () => {
    const p = withState('inactive');
    show([p]);
    api.reject.mockRejectedValueOnce(
      new ReviewApiError(409, 'stale_view', 'stale', {
        code: 'stale_view',
        proposal: {
          id: p.id,
          seen_version: 'v-new',
          status: 'proposed',
          patch: p.patch,
          current_values: p.current_values,
          expected_version: 'x',
          target_changed_at: null,
        },
      }),
    );
    api.get.mockResolvedValue({ ...p, seen_version: 'v-new' });
    renderPage('/review?tab=look');
    const card = await findCard(p);
    fireEvent.click(card.getByLabelText(INACTIVE_TICK_LABEL));
    expect(card.getByRole('button', { name: 'Accept' })).toBeEnabled();
    fireEvent.click(card.getByRole('button', { name: 'Reject' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Wrong record' }));
    fireEvent.click(within(dialog).getByRole('button', { name: 'Reject' }));
    await waitFor(() => expect(api.get).toHaveBeenCalled());
    await waitFor(() => expect(within(cardEl(p)).getByLabelText(INACTIVE_TICK_LABEL)).not.toBeChecked());
    await waitFor(() => expect(within(cardEl(p)).getByRole('button', { name: 'Accept' })).toBeDisabled());
  });
});

describe('the changed box is worded by what changed', () => {
  it('values changed: "compare the values" with its tick, no state notice', async () => {
    const p = withState('present', { target_changed_at: '2026-11-19T08:00:00Z' });
    show([p]);
    renderPage('/review?tab=look');
    const card = await findCard(p);
    expect(card.getByTestId('record-changed')).toHaveTextContent('Compare them with the suggestion');
    expect(card.queryByTestId('target-state')).not.toBeInTheDocument();
    expect(card.getByTestId('accept-blocked-reason')).toHaveTextContent('I have compared the current values');
  });

  it('state changed: the state notice, not "compare the values"', async () => {
    const p = withState('moved', { target_changed_at: '2026-11-19T08:00:00Z' });
    show([p]);
    renderPage('/review?tab=look');
    const card = await findCard(p);
    expect(card.getByTestId('target-state')).toHaveTextContent(REASONS.moved);
    expect(card.getByTestId('target-state')).toHaveTextContent('since');
    expect(card.queryByTestId('record-changed')).not.toBeInTheDocument();
    expect(card.queryByLabelText('I have compared the current values')).not.toBeInTheDocument();
  });

  it('keeps showing the last refusal while the record is marked changed', async () => {
    const p = withState('present', {
      target_changed_at: '2026-11-19T08:00:00Z',
      last_apply_error: 'The record refused the values: phone is too long.',
    });
    show([p]);
    renderPage('/review?tab=look');
    expect((await findCard(p)).getByTestId('apply-error')).toHaveTextContent('phone is too long');
  });
});

describe('refusals carry the server’s reason', () => {
  it('a 409 record_changed shows what changed', async () => {
    const p = withState('present');
    show([p]);
    api.accept.mockRejectedValueOnce(
      new ReviewApiError(
        409,
        'record_changed',
        'The record changed after this proposal was made. ' + REASONS.inactive,
        {
          code: 'record_changed',
          target_state: 'inactive',
          target_state_reason: REASONS.inactive,
        },
      ),
    );
    api.get.mockResolvedValue({
      ...p,
      seen_version: 'v-2',
      target_state: 'inactive',
      target_state_reason: REASONS.inactive,
      target_changed_at: '2026-11-19T09:00:00Z',
    });
    renderPage();
    fireEvent.click((await findCard(p)).getByRole('button', { name: 'Accept' }));
    expect(await screen.findByTestId('card-notice')).toHaveTextContent(
      `Nothing was applied: the record changed after this was suggested. ${REASONS.inactive}`,
    );
    expect(await within(cardEl(p)).findByTestId('target-state')).toHaveTextContent(REASONS.inactive);
  });

  it('a 409 not_acceptable says nothing was applied, with the reason', async () => {
    const p = withState('present');
    show([p]);
    api.accept.mockRejectedValueOnce(
      new ReviewApiError(409, 'not_acceptable', REASONS.moved, { code: 'not_acceptable' }),
    );
    api.get.mockResolvedValue({ ...p, seen_version: 'v-3', target_state: 'moved', target_state_reason: REASONS.moved });
    renderPage();
    fireEvent.click((await findCard(p)).getByRole('button', { name: 'Accept' }));
    expect(await screen.findByTestId('card-notice')).toHaveTextContent(`Nothing was applied. ${REASONS.moved}`);
  });

  it('an older server that does not know acknowledge_inactive gets a plain explanation', async () => {
    const p = withState('inactive');
    show([p]);
    api.accept.mockRejectedValueOnce(new ReviewApiError(400, 'invalid', 'Unknown keys: acknowledge_inactive'));
    api.get.mockResolvedValue(p);
    renderPage('/review?tab=look');
    const card = await findCard(p);
    fireEvent.click(card.getByLabelText(INACTIVE_TICK_LABEL));
    fireEvent.click(card.getByRole('button', { name: 'Accept' }));
    expect(await screen.findByTestId('card-notice')).toHaveTextContent(
      'does not accept changes to inactive records yet',
    );
  });
});

describe('older backends', () => {
  it('without target_state there is no state notice and the buttons behave as before', async () => {
    const p = makeProposal({ seen_version: 'v-old' });
    show([p]);
    api.accept.mockResolvedValue({ ...p, status: 'accepted', applied_patch: p.patch });
    renderPage();
    const card = await findCard(p);
    expect(card.queryByTestId('target-state')).not.toBeInTheDocument();
    fireEvent.click(card.getByRole('button', { name: 'Accept' }));
    await waitFor(() => expect(api.accept).toHaveBeenCalledWith(p.id, 'v-old'));
  });
});

describe('watched fields', () => {
  it('marks values that will change, values already set, and context', () => {
    const p = makeProposal({
      patch: { city: 'Krabi', phone: '+66 2 000 0000' },
      current_values: { city: 'Trang', phone: '+66 2 000 0000', email: 'front@example.com' },
      watched_fields: ['city', 'phone'],
    });
    render(<ChangePreview proposal={p} valuesFollowTarget />);
    expect(screen.getByTestId('row-role-city')).toHaveTextContent('Will change');
    expect(screen.getByTestId('row-role-phone')).toHaveTextContent('Already this value');
    expect(screen.getByTestId('context-row-email')).toHaveTextContent('Context, not changed by this suggestion');
  });

  it('a note says it is added to the notes as they are when you accept, with the notes as context', () => {
    const p = makeProposal({
      kind: 'note',
      patch: { notes: 'New line' },
      current_values: { notes: 'Older notes' },
      watched_fields: [],
    });
    render(<ChangePreview proposal={p} valuesFollowTarget />);
    expect(screen.getByTestId('note-wording')).toHaveTextContent(
      'This is added to the notes as they are when you accept',
    );
    expect(screen.getByTestId('note-wording')).toHaveTextContent('shown for context');
    expect(screen.getByText('Older notes')).toBeInTheDocument();
  });

  it('without watched_fields nothing is labelled', () => {
    render(<ChangePreview proposal={makeProposal()} />);
    expect(screen.queryByTestId('row-role-phone')).not.toBeInTheDocument();
  });
});

describe('expiry line', () => {
  it('uses the exact count from the summary when the API sends it', async () => {
    api.listOpen.mockResolvedValue(page([makeProposal()], 900));
    api.list.mockResolvedValue(page([], 900, { open_expiring_within_days: 7, open_expiring_count: 12 }));
    renderPage();
    expect(await screen.findByTestId('expiring-soon')).toHaveTextContent(
      '12 open suggestions expire within 7 days. Some of them may not be in this list.',
    );
    expect(api.listOpen).not.toHaveBeenCalledWith(1, 'expiring');
  });
});
