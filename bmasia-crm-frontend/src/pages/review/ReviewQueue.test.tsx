/* eslint-disable testing-library/no-node-access, testing-library/no-container -- these tests check that
   elements such as <img>, <script> and links are absent, and read data attributes on cards. */
import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import ReviewQueue from './ReviewQueue';
import ChangePreview from './ChangePreview';
import CompanyReviewLink from './CompanyReviewLink';
import reviewApi, { ChangeProposal, ReviewApiError } from '../../services/reviewApi';
import { buildNavGroups } from '../../components/navigation';
import { makeProposal, settingsOn } from './testFixtures';
import { resetReviewSettingsCache } from './useReviewStatus';
import { CONFLICT_REJECT_REASON } from './reviewModel';

/** Built at run time so the source holds no script URL literal. */
const JS = ['java', 'script:'].join('');

// No HTTP in these tests: the shared axios instance is replaced and every API call is mocked below.
jest.mock('../../services/authService', () => ({ __esModule: true, default: {}, authApi: {} }));

jest.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ user: { username: 'reviewer.one' } }),
}));

jest.mock('../../services/reviewApi', () => {
  const actual = jest.requireActual('../../services/reviewApi');
  return {
    __esModule: true,
    ...actual,
    default: {
      getSettings: jest.fn(),
      listAllOpen: jest.fn(),
      list: jest.fn(),
      openCount: jest.fn(),
      get: jest.fn(),
      accept: jest.fn(),
      acceptWithEdits: jest.fn(),
      reject: jest.fn(),
      reopen: jest.fn(),
      bulkReject: jest.fn(),
      getContact: jest.fn(),
    },
  };
});

const api = reviewApi as jest.Mocked<typeof reviewApi>;

let location: ReturnType<typeof useLocation> | null = null;
const Where: React.FC = () => {
  location = useLocation();
  return null;
};

const renderPage = (entry = '/review') =>
  render(
    <MemoryRouter initialEntries={[entry]}>
      <Where />
      <Routes>
        <Route path="/review" element={<ReviewQueue />} />
      </Routes>
    </MemoryRouter>,
  );

const withOpen = (rows: ChangeProposal[], settings = settingsOn) => {
  api.getSettings.mockResolvedValue(settings);
  api.listAllOpen.mockResolvedValue({ rows, count: rows.length, truncated: false });
};

const cardOf = (p: ChangeProposal) => {
  const el = document.querySelector(`[data-proposal-id="${p.id}"]`);
  if (!el) throw new Error(`card ${p.id} not shown`);
  return within(el as HTMLElement);
};

const findCard = async (p: ChangeProposal) => {
  await waitFor(() => expect(document.querySelector(`[data-proposal-id="${p.id}"]`)).not.toBeNull());
  return cardOf(p);
};

const conflictError = (code: string, proposal?: Partial<ChangeProposal>) =>
  new ReviewApiError(409, code, `refused: ${code}`, proposal ? { code, proposal } : { code });

beforeEach(() => {
  jest.resetAllMocks();
  resetReviewSettingsCache();
  api.getContact.mockResolvedValue({ name: 'Pat Example', is_primary: false, contact_type: 'Other' });
  api.list.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
});

// ------------------------------------------------------------------ states

describe('states', () => {
  it('explains that suggestions are switched off and shows nothing else', async () => {
    api.getSettings.mockResolvedValue({ ...settingsOn, proposals_enabled: false });
    renderPage();
    expect(await screen.findByText('Suggestions are not switched on yet')).toBeInTheDocument();
    expect(api.listAllOpen).not.toHaveBeenCalled();
    expect(screen.queryByRole('tab')).not.toBeInTheDocument();
  });

  it('shows an error with a retry when the settings cannot be read', async () => {
    api.getSettings.mockRejectedValueOnce(new ReviewApiError(undefined, 'no_answer', 'No answer'));
    renderPage();
    expect(await screen.findByText(/review settings could not be read/)).toBeInTheDocument();
    api.getSettings.mockResolvedValue({ ...settingsOn, proposals_enabled: false });
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('Suggestions are not switched on yet')).toBeInTheDocument();
  });

  it('shows an error when the list cannot be loaded, and an empty state per tab', async () => {
    api.getSettings.mockResolvedValue(settingsOn);
    api.listAllOpen.mockRejectedValueOnce(new ReviewApiError(500, undefined, 'boom'));
    renderPage();
    expect(await screen.findByText(/could not be loaded/)).toBeInTheDocument();
    api.listAllOpen.mockResolvedValue({ rows: [], count: 0, truncated: false });
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('Nothing waiting for review')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('tab', { name: /Needs another look/ }));
    expect(await screen.findByText('Nothing needs another look')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('tab', { name: 'Decided' }));
    expect(await screen.findByText('No decided suggestions yet')).toBeInTheDocument();
  });

  it('is read-only with one line of reason when the API says the user may not review', async () => {
    const p = makeProposal();
    withOpen([p], { ...settingsOn, you_can_review: false, review_refusal: 'Not on the list of reviewers.' });
    renderPage();
    expect(await screen.findByTestId('page-read-only')).toHaveTextContent('Not on the list of reviewers.');
    expect(cardOf(p).queryByRole('button', { name: 'Accept' })).not.toBeInTheDocument();
    expect(cardOf(p).getByTestId('read-only-reason')).toHaveTextContent('Not on the list of reviewers.');
  });

  it('keeps the proposer and the evidence recorder from deciding their own suggestion', async () => {
    const own = makeProposal({ proposer_username: 'Reviewer.One' });
    const recorded = makeProposal({
      evidence_recorded_by: 'reviewer.one',
      patch: { city: 'Krabi' },
      current_values: { city: 'Trang' },
    });
    withOpen([own, recorded]);
    renderPage();
    await screen.findAllByTestId('proposal-card');
    expect(cardOf(own).getByTestId('read-only-reason')).toHaveTextContent('You made this suggestion');
    expect(cardOf(own).queryByRole('button', { name: 'Accept' })).not.toBeInTheDocument();
    expect(cardOf(recorded).getByTestId('read-only-reason')).toHaveTextContent('You recorded the evidence');
  });

  it('shows a suggestion that expired while on screen as expired, without decisions', async () => {
    const p = makeProposal({ expires_at: '2020-01-01T00:00:00Z' });
    withOpen([p]);
    renderPage();
    expect(await screen.findByTestId('expired-on-screen')).toBeInTheDocument();
    expect(cardOf(p).queryByRole('button', { name: 'Accept' })).not.toBeInTheDocument();
  });
});

// ------------------------------------------------------------------ rendering

describe('cards', () => {
  it('renders each kind and each evidence state', async () => {
    const rows = [
      makeProposal({ kind: 'field_update', evidence: 'verified_captured' }),
      makeProposal({
        kind: 'note',
        evidence: 'verified_agent_recorded',
        patch: { notes: 'Lobby closes in January.' },
        current_values: { notes: 'Older note' },
      }),
      makeProposal({
        kind: 'new_contact',
        target_collection: 'contact',
        target_id: '',
        evidence: 'unverified',
        evidence_quote: '',
        activity_id: null,
        patch: { name: 'Dana Example', email: 'dana@example.com', title: 'Manager' },
        current_values: {},
      }),
      makeProposal({
        kind: 'task',
        target_collection: 'task',
        target_id: '',
        evidence: 'unverified',
        patch: { title: 'Call back', priority: 'High', due_date: '2026-11-20T09:00:00Z' },
        current_values: {},
      }),
    ];
    withOpen(rows);
    renderPage();
    expect(await screen.findAllByTestId('proposal-card')).toHaveLength(4);
    expect(screen.getByText('Update fields')).toBeInTheDocument();
    expect(screen.getByText('Text to add to the notes')).toBeInTheDocument();
    expect(screen.getByTestId('note-text')).toHaveTextContent('Lobby closes in January.');
    expect(screen.getByText('New contact with')).toBeInTheDocument();
    expect(screen.getByText('dana@example.com')).toBeInTheDocument();
    expect(screen.getByTestId('email-caution')).toBeInTheDocument();
    expect(screen.getByText('New task with')).toBeInTheDocument();
    expect(screen.getByText('Call back')).toBeInTheDocument();
    expect(document.querySelector('[data-evidence="verified_captured"]')).toHaveTextContent('From captured mail');
    expect(document.querySelector('[data-evidence="verified_agent_recorded"]')).toHaveTextContent(
      'From text an agent recorded',
    );
    expect(document.querySelectorAll('[data-evidence="unverified"]')[0]).toHaveTextContent('No evidence attached');
  });

  it('warns on a primary contact', async () => {
    const p = makeProposal({
      target_collection: 'contact',
      target_id: 'k1',
      patch: { title: 'Owner' },
      current_values: { title: 'GM' },
    });
    api.getContact.mockResolvedValue({ name: 'Kim Example', is_primary: true, contact_type: 'Primary' });
    withOpen([p]);
    renderPage();
    expect(await screen.findByTestId('role-contact')).toHaveTextContent('primary contact');
    expect(cardOf(p).getAllByText('Kim Example').length).toBeGreaterThan(0);
  });

  it('shows a last apply error and an API mixed-script warning prominently', async () => {
    const p = makeProposal({
      last_apply_error: 'The record refused the values',
      patch: { city: 'Sample' },
      current_values: { city: 'Other' },
      warnings: [{ field: 'city', code: 'mixed_script', detail: 'x' }],
    });
    withOpen([p]);
    renderPage('/review?tab=look');
    expect(await screen.findByTestId('apply-error')).toHaveTextContent('The record refused the values');
    expect(screen.getByText('Mixed alphabets')).toBeInTheDocument();
  });
});

describe('before and after for each allowlisted field', () => {
  const fields: [string, string][] = [];
  Object.entries(settingsOn.kinds.field_update).forEach(([collection, keys]) =>
    keys.forEach((k) => fields.push([collection, k])),
  );

  it.each(fields)('%s.%s', (collection, key) => {
    const p = makeProposal({
      target_collection: collection as 'company',
      patch: { [key]: `new ${key}` },
      current_values: { [key]: `old ${key}` },
    });
    render(<ChangePreview proposal={p} />);
    const before = screen.getByTestId(`before-${key}`);
    expect(before).toHaveTextContent(`old ${key}`);
    expect(before).toHaveStyle('text-decoration: line-through');
    expect(screen.getByTestId(`after-${key}`)).toHaveTextContent(`new ${key}`);
  });

  it('shows "empty" for a field that is empty now, or would be cleared', () => {
    render(<ChangePreview proposal={makeProposal({ patch: { city: null }, current_values: { city: '' } })} />);
    expect(screen.getAllByText('empty')).toHaveLength(2);
  });
});

// ------------------------------------------------------------------ decisions

describe('decisions', () => {
  it('accepts with the seen_version and collapses into one line with a link that opens in a new tab', async () => {
    const p = makeProposal({ seen_version: 'v-shown' });
    withOpen([p]);
    api.accept.mockResolvedValue({ ...p, status: 'accepted', applied_patch: p.patch });
    renderPage();
    fireEvent.click(await (await findCard(p)).findByRole('button', { name: 'Accept' }));
    expect(await screen.findByTestId('proposal-result')).toHaveTextContent('Accepted: Phone “+66 2 111 2222” saved');
    expect(api.accept).toHaveBeenCalledWith(p.id, 'v-shown');
    const link = within(screen.getByTestId('proposal-result')).getByRole('link', { name: /Open company/ });
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    expect(link).toHaveAttribute('href', `/companies/${p.company_id}`);
  });

  it('never submits twice while a decision is in flight', async () => {
    const p = makeProposal();
    withOpen([p]);
    let finish: (v: ChangeProposal) => void = () => undefined;
    api.accept.mockReturnValue(new Promise((resolve) => (finish = resolve)));
    renderPage();
    const button = await (await findCard(p)).findByRole('button', { name: 'Accept' });
    fireEvent.click(button);
    fireEvent.click(button);
    expect(api.accept).toHaveBeenCalledTimes(1);
    expect(cardOf(p).getByRole('button', { name: 'Saving…' })).toBeDisabled();
    expect(cardOf(p).getByRole('button', { name: 'Reject' })).toBeDisabled();
    await act(async () => finish({ ...p, status: 'accepted', applied_patch: p.patch }));
    expect(await screen.findByTestId('proposal-result')).toBeInTheDocument();
  });

  it('on 409 stale_view refreshes the card, explains it and waits for a fresh click (no retry)', async () => {
    const p = makeProposal({ seen_version: 'v1' });
    withOpen([p]);
    const fresh = { ...p, seen_version: 'v2', current_values: { phone: '+66 2 333 4444' } };
    api.accept.mockRejectedValueOnce(
      conflictError('stale_view', {
        id: p.id,
        seen_version: 'v2',
        status: 'proposed',
        patch: p.patch,
        current_values: fresh.current_values,
        expected_version: 'x',
        target_changed_at: null,
      }),
    );
    api.get.mockResolvedValue(fresh);
    renderPage();
    fireEvent.click(await (await findCard(p)).findByRole('button', { name: 'Accept' }));
    expect(await screen.findByTestId('card-notice')).toHaveTextContent('Nothing was done');
    expect(screen.getByTestId('card-notice')).toHaveTextContent('the current Phone was re-read');
    expect(api.get).toHaveBeenCalledWith(p.id);
    expect(api.accept).toHaveBeenCalledTimes(1);
    expect(await screen.findByTestId('before-phone')).toHaveTextContent('+66 2 333 4444');
    api.accept.mockResolvedValueOnce({ ...fresh, status: 'accepted', applied_patch: p.patch });
    fireEvent.click(cardOf(p).getByRole('button', { name: 'Accept' }));
    await waitFor(() => expect(api.accept).toHaveBeenLastCalledWith(p.id, 'v2'));
  });

  it('on 409 record_changed shows the re-read values and requires looking again before accepting', async () => {
    const p = makeProposal({ seen_version: 'v1' });
    withOpen([p]);
    const fresh = {
      ...p,
      seen_version: 'v3',
      target_changed_at: '2026-11-18T08:00:00Z',
      current_values: { phone: '+66 2 999 0000' },
    };
    api.accept.mockRejectedValueOnce(
      conflictError('record_changed', {
        id: p.id,
        seen_version: 'v3',
        status: 'proposed',
        patch: p.patch,
        current_values: fresh.current_values,
        expected_version: 'y',
        target_changed_at: fresh.target_changed_at,
      }),
    );
    api.get.mockResolvedValue(fresh);
    renderPage();
    fireEvent.click(await (await findCard(p)).findByRole('button', { name: 'Accept' }));
    expect(await screen.findByTestId('card-notice')).toHaveTextContent('Nothing was applied: the record changed');
    expect(await screen.findByTestId('record-changed')).toBeInTheDocument();
    expect(screen.getByTestId('before-phone')).toHaveTextContent('+66 2 999 0000');
    const accept = cardOf(p).getByRole('button', { name: 'Accept' });
    expect(accept).toBeDisabled();
    fireEvent.click(screen.getByLabelText('I have compared the current values'));
    expect(cardOf(p).getByRole('button', { name: 'Accept' })).toBeEnabled();
    expect(api.accept).toHaveBeenCalledTimes(1);
  });

  it('on 403 reviewer_is_party makes that card read-only; on human_review_required the whole page', async () => {
    const a = makeProposal();
    const b = makeProposal({ patch: { city: 'X' }, current_values: { city: 'Y' } });
    withOpen([a, b]);
    api.accept.mockRejectedValueOnce(
      new ReviewApiError(403, 'reviewer_is_party', 'A reviewer must be a different person from the proposer.'),
    );
    renderPage();
    fireEvent.click(await (await findCard(a)).findByRole('button', { name: 'Accept' }));
    expect(await (await findCard(a)).findByTestId('read-only-reason')).toHaveTextContent(
      'different person from the proposer',
    );
    expect(cardOf(b).getByRole('button', { name: 'Accept' })).toBeEnabled();
    api.accept.mockRejectedValueOnce(
      new ReviewApiError(403, 'human_review_required', 'Agent accounts cannot decide on proposals.'),
    );
    fireEvent.click(cardOf(b).getByRole('button', { name: 'Accept' }));
    expect(await screen.findByTestId('page-read-only')).toHaveTextContent('Agent accounts cannot decide');
    expect(screen.queryByRole('button', { name: 'Accept' })).not.toBeInTheDocument();
  });

  it('on 409 expired shows the suggestion as expired', async () => {
    const p = makeProposal();
    withOpen([p]);
    api.accept.mockRejectedValueOnce(conflictError('expired'));
    api.get.mockResolvedValue({ ...p, status: 'expired' });
    renderPage();
    fireEvent.click(await (await findCard(p)).findByRole('button', { name: 'Accept' }));
    expect(await screen.findByTestId('proposal-result')).toHaveTextContent('expired. Nothing was applied');
  });

  it('when no answer comes back, re-reads the suggestion instead of retrying', async () => {
    const p = makeProposal();
    withOpen([p]);
    api.accept.mockRejectedValueOnce(new ReviewApiError(undefined, 'no_answer', 'No answer from the server.'));
    api.get.mockResolvedValue({ ...p, status: 'accepted', reviewer_username: 'reviewer.one', applied_patch: p.patch });
    renderPage();
    fireEvent.click(await (await findCard(p)).findByRole('button', { name: 'Accept' }));
    expect(await screen.findByTestId('proposal-result')).toHaveTextContent('Already accepted');
    expect(api.accept).toHaveBeenCalledTimes(1);
    expect(api.get).toHaveBeenCalledWith(p.id);
  });

  it('shows the refusal reason for a person-only change', async () => {
    const p = makeProposal();
    withOpen([p]);
    api.accept.mockRejectedValueOnce(
      new ReviewApiError(
        422,
        'person_only_change',
        'A change to its email must be made by a person on the contact page.',
      ),
    );
    api.get.mockResolvedValue({
      ...p,
      last_apply_error: 'A change to its email must be made by a person on the contact page.',
    });
    renderPage();
    fireEvent.click(await (await findCard(p)).findByRole('button', { name: 'Accept' }));
    expect(await screen.findByTestId('card-notice')).toHaveTextContent('must be made by a person on the contact page');
  });

  it('rejects only with a reason, sending the seen_version', async () => {
    const p = makeProposal({ seen_version: 'v-r' });
    withOpen([p]);
    api.reject.mockResolvedValue({ ...p, status: 'rejected' });
    renderPage();
    fireEvent.click(await (await findCard(p)).findByRole('button', { name: 'Reject' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Reject' }));
    expect(await within(dialog).findByText('Required.')).toBeInTheDocument();
    expect(api.reject).not.toHaveBeenCalled();
    fireEvent.click(within(dialog).getByRole('button', { name: 'Wrong record' }));
    fireEvent.click(within(dialog).getByRole('button', { name: 'Reject' }));
    await waitFor(() => expect(api.reject).toHaveBeenCalledWith(p.id, 'v-r', 'Wrong record'));
    expect(await screen.findByTestId('proposal-result')).toHaveTextContent('Rejected. Reason: Wrong record');
  });

  it('edits then accepts only the changed fields, with hints the API enforces', async () => {
    const p = makeProposal({
      seen_version: 'v-e',
      patch: { website: 'https://new.example.com', city: 'Hua Hin' },
      current_values: { website: '', city: 'Cha-am' },
    });
    withOpen([p]);
    api.acceptWithEdits.mockResolvedValue({
      ...p,
      status: 'edited',
      applied_patch: { website: 'https://www.new.example.com' },
    });
    renderPage();
    fireEvent.click(await (await findCard(p)).findByRole('button', { name: 'Edit' }));
    const website = cardOf(p).getByLabelText('Website');
    fireEvent.change(website, { target: { value: `${JS}alert(1)` } });
    expect(cardOf(p).getByText('Must start with http:// or https://.')).toBeInTheDocument();
    fireEvent.click(cardOf(p).getByRole('button', { name: 'Accept with edits' }));
    expect(api.acceptWithEdits).not.toHaveBeenCalled();
    fireEvent.change(website, { target: { value: 'https://www.new.example.com' } });
    const leaveOut = cardOf(p).getAllByLabelText('Leave out');
    fireEvent.click(leaveOut[1]);
    fireEvent.click(cardOf(p).getByRole('button', { name: 'Accept with edits' }));
    await waitFor(() =>
      expect(api.acceptWithEdits).toHaveBeenCalledWith(p.id, 'v-e', { website: 'https://www.new.example.com' }, [
        'city',
      ]),
    );
    expect(await screen.findByTestId('proposal-result')).toHaveTextContent('Accepted with your edits');
  });

  it('makes the reviewer pick one of two conflicting suggestions, and rejects the other', async () => {
    const a = makeProposal({
      id: 'aaaaaaaa-0000-4000-8000-000000000001',
      seen_version: 'va',
      patch: { email: 'a@example.com' },
      current_values: { email: 'old@example.com' },
    });
    const b = makeProposal({
      id: 'bbbbbbbb-0000-4000-8000-000000000002',
      seen_version: 'vb',
      proposer_username: 'other-agent',
      patch: { email: 'b@example.com' },
      current_values: { email: 'old@example.com' },
    });
    a.conflicts_with = [
      {
        id: b.id,
        proposer_username: 'other-agent',
        patch: { email: 'b@example.com' },
        evidence_occurred_at: null,
        created_at: b.created_at,
      },
    ];
    b.conflicts_with = [
      {
        id: a.id,
        proposer_username: a.proposer_username,
        patch: { email: 'a@example.com' },
        evidence_occurred_at: null,
        created_at: a.created_at,
      },
    ];
    withOpen([a, b]);
    api.accept.mockResolvedValue({ ...a, status: 'accepted', applied_patch: a.patch });
    api.reject.mockResolvedValue({ ...b, status: 'rejected' });
    renderPage('/review?tab=look');
    const accept = await (await findCard(a)).findByRole('button', { name: 'Accept and reject the other' });
    expect(accept).toBeDisabled();
    fireEvent.click(cardOf(a).getByRole('button', { name: 'Keep this one' }));
    fireEvent.click(cardOf(a).getByRole('button', { name: 'Accept and reject the other' }));
    await waitFor(() => expect(api.reject).toHaveBeenCalledWith(b.id, 'vb', CONFLICT_REJECT_REASON));
    expect(api.accept).toHaveBeenCalledWith(a.id, 'va');
    expect(await screen.findByText(/The other suggestion by other-agent was rejected/)).toBeInTheDocument();
  });

  it('bulk rejects a selected batch with one reason, sending each seen_version; there is no bulk accept', async () => {
    const a = makeProposal({ batch_key: 'mail-1', seen_version: 'va' });
    const b = makeProposal({
      batch_key: 'mail-1',
      seen_version: 'vb',
      patch: { city: 'X' },
      current_values: { city: 'Y' },
    });
    withOpen([a, b]);
    api.bulkReject.mockResolvedValue({
      rejected: [a.id],
      skipped: [{ id: b.id, status: 'proposed', code: 'stale_view' }],
      not_found: [],
    });
    api.get.mockResolvedValue({ ...b, seen_version: 'vb2' });
    renderPage();
    fireEvent.click(await screen.findByLabelText('Select the batch to reject it'));
    const bar = screen.getByTestId('bulk-bar');
    expect(bar).toHaveTextContent('2 selected');
    expect(within(bar).queryByRole('button', { name: /accept/i })).not.toBeInTheDocument();
    fireEvent.click(within(bar).getByRole('button', { name: 'Reject selected…' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.change(within(dialog).getByLabelText('Reason'), { target: { value: 'Not worth recording' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Reject 2' }));
    await waitFor(() =>
      expect(api.bulkReject).toHaveBeenCalledWith(
        [
          { id: a.id, seen_version: 'va' },
          { id: b.id, seen_version: 'vb' },
        ],
        'Not worth recording',
      ),
    );
    expect(await (await findCard(b)).findByTestId('card-notice')).toHaveTextContent('changed since it was loaded');
    expect(cardOf(a).getByText(/Rejected. Reason: Not worth recording/)).toBeInTheDocument();
  });

  it('reopens a rejected suggestion from the Decided tab with a note', async () => {
    const p = makeProposal({
      status: 'rejected',
      seen_version: 'v-x',
      reviewer_username: 'second.person',
      reviewed_at: '2026-11-18T09:00:00Z',
      decision_note: 'Wrong record',
      history: [{ action: 'rejected', by: 'second.person', at: '2026-11-18T09:00:00Z', note: 'Wrong record' }],
    });
    withOpen([]);
    api.list.mockResolvedValue({ count: 1, next: null, previous: null, results: [p] });
    api.reopen.mockResolvedValue({ ...p, status: 'proposed' });
    renderPage('/review?tab=decided');
    expect(await screen.findByTestId('decided-line')).toHaveTextContent('Rejected by second.person');
    fireEvent.click(screen.getByRole('button', { name: 'Reopen' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.change(within(dialog).getByLabelText('Note'), { target: { value: 'It was the right record after all' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Reopen' }));
    await waitFor(() => expect(api.reopen).toHaveBeenCalledWith(p.id, 'v-x', 'It was the right record after all'));
  });
});

// ------------------------------------------------------------------ keyboard

describe('keyboard', () => {
  it('a accepts only after the card has been in focus for a moment', async () => {
    const p = makeProposal({ seen_version: 'v-k' });
    withOpen([p]);
    api.accept.mockResolvedValue({ ...p, status: 'accepted', applied_patch: p.patch });
    renderPage();
    await screen.findByTestId('proposal-card');
    fireEvent.keyDown(window, { key: 'j' });
    await waitFor(() => expect(document.activeElement).toBe(screen.getByTestId('proposal-card')));
    fireEvent.keyDown(window, { key: 'a' });
    expect(await screen.findByText(/Read the card first/)).toBeInTheDocument();
    expect(api.accept).not.toHaveBeenCalled();
    await act(() => new Promise((resolve) => setTimeout(resolve, 1700)));
    fireEvent.keyDown(window, { key: 'a' });
    await waitFor(() => expect(api.accept).toHaveBeenCalledWith(p.id, 'v-k'));
  });
});

// ------------------------------------------------------------------ URL state

describe('URL state', () => {
  it('reads tab and filters from the URL and writes changes back', async () => {
    withOpen([]);
    renderPage('/review?tab=decided&kind=note&proposer=example-agent');
    await waitFor(() =>
      expect(api.list).toHaveBeenCalledWith(
        expect.objectContaining({ kind: ['note'], proposer: 'example-agent', page: 1 }),
      ),
    );
    expect(api.list.mock.calls[0][0].status).toEqual([
      'accepted',
      'edited',
      'rejected',
      'expired',
      'superseded',
      'failed',
    ]);
    fireEvent.click(screen.getByRole('tab', { name: /Open/ }));
    await waitFor(() => expect(location?.search).toBe('?kind=note&proposer=example-agent'));
  });

  it('filters the open list by evidence state from the URL', async () => {
    const a = makeProposal({ evidence: 'unverified', company_name: 'Unverified Inn', company_id: 'u1' });
    const b = makeProposal({ evidence: 'verified_captured', company_name: 'Captured Lodge', company_id: 'c2' });
    withOpen([a, b]);
    renderPage('/review?evidence=unverified');
    expect(await screen.findAllByText('Unverified Inn')).not.toHaveLength(0);
    expect(screen.queryByText('Captured Lodge')).not.toBeInTheDocument();
  });
});

// ------------------------------------------------------------------ hostile values

describe('plain text only', () => {
  it('renders tags, script URLs, markdown and bidi controls as text', async () => {
    const spies = [jest.spyOn(console, 'error'), jest.spyOn(console, 'warn'), jest.spyOn(console, 'log')];
    const p = makeProposal({
      company_name: '<b>Bold Co</b>',
      patch: { address_line1: '<img src=x onerror=alert(1)>' },
      current_values: { address_line1: 'Old Road' },
      evidence_quote: `see [here](${JS}alert(1)) <script>alert(2)</script> ab\u202Ecd`,
      evidence_source_url: `${JS}alert(1)`,
      rationale: '**bold** https://phish.example.com',
      proposer_username: '<i>agent</i>',
    });
    withOpen([p]);
    api.accept.mockRejectedValueOnce(
      new ReviewApiError(422, 'invalid_value', 'refused', { errors: { address_line1: ['bad'] } }),
    );
    api.get.mockResolvedValue(p);
    const { container } = renderPage();
    await screen.findByTestId('proposal-card');
    expect(container.querySelector('img')).toBeNull();
    expect(container.querySelector('script')).toBeNull();
    expect(container.querySelector('b')).toBeNull();
    expect(screen.getByTestId('after-address_line1')).toHaveTextContent('<img src=x onerror=alert(1)>');
    expect(screen.getAllByText('<b>Bold Co</b>').length).toBeGreaterThan(0);
    expect(screen.queryByRole('link', { name: /Open source/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /here/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /phish/ })).not.toBeInTheDocument();
    const quote = screen.getByTestId('evidence-quote');
    expect(quote.textContent).not.toContain('\u202E');
    expect(quote.querySelector('[data-hidden-char="U+202E"]')).not.toBeNull();
    Array.from(container.querySelectorAll('a')).forEach((a) => {
      const href = a.getAttribute('href') || '';
      expect(href.startsWith('/') || /^https?:\/\//.test(href)).toBe(true);
    });
    // A refusal does not log the proposal or the request body.
    fireEvent.click(screen.getByRole('button', { name: 'Accept' }));
    expect(await screen.findByTestId('card-notice')).toHaveTextContent('Address line 1: bad');
    spies.forEach((spy) => {
      spy.mock.calls.forEach((args) => expect(JSON.stringify(args)).not.toMatch(/onerror|script:alert|phish/));
      spy.mockRestore();
    });
  });

  it('links the source only for an http(s) URL, with noopener', async () => {
    const p = makeProposal({ evidence_source_url: 'https://mail.example.com/m/1' });
    withOpen([p]);
    renderPage();
    const link = await screen.findByRole('link', { name: /Open source/ });
    expect(link).toHaveAttribute('href', 'https://mail.example.com/m/1');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    expect(link).toHaveAttribute('target', '_blank');
  });
});

// ------------------------------------------------------------------ menu and company link

describe('menu entry and company link', () => {
  it('shows Review next to Today only when switched on, with the open count', () => {
    const off = buildNavGroups(0)[0].items.map((i) => i.path);
    expect(off).not.toContain('/review');
    const items = buildNavGroups(0, { enabled: true, openCount: 7 })[0].items;
    expect(items.map((i) => i.path)).toEqual(['/today', '/review', '/dashboard']);
    expect(items[1].badge).toBe(7);
    expect(buildNavGroups(0, { enabled: true, openCount: 0 })[0].items[1].badge).toBeUndefined();
  });

  const renderLink = () =>
    render(
      <MemoryRouter>
        <CompanyReviewLink companyId="c-42" />
      </MemoryRouter>,
    );

  it('links a company to its open suggestions when switched on and above zero', async () => {
    api.getSettings.mockResolvedValue(settingsOn);
    api.openCount.mockResolvedValue(3);
    renderLink();
    const link = await screen.findByTestId('company-review-link');
    expect(link).toHaveTextContent('3 suggestions to review');
    expect(link).toHaveAttribute('href', '/review?company=c-42');
    expect(api.openCount).toHaveBeenCalledWith('c-42');
  });

  it('shows nothing on the company page when switched off', async () => {
    api.getSettings.mockResolvedValue({ ...settingsOn, proposals_enabled: false });
    renderLink();
    await waitFor(() => expect(api.getSettings).toHaveBeenCalled());
    expect(screen.queryByTestId('company-review-link')).not.toBeInTheDocument();
    expect(api.openCount).not.toHaveBeenCalled();
  });
});
