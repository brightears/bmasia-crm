/* eslint-disable testing-library/no-node-access, testing-library/prefer-screen-queries -- these tests query inside
   one card on purpose (several cards show the same buttons), and read data attributes and focus on cards. */
import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ReviewQueue from './ReviewQueue';
import reviewApi, { ChangeProposal, ReviewApiError } from '../../services/reviewApi';
import { makeProposal, settingsOn } from './testFixtures';
import { resetReviewSettingsCache } from './useReviewStatus';

// No HTTP in these tests: the shared axios instance is replaced and every API call is mocked below.
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

const renderPage = (entry = '/review') =>
  render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/review" element={<ReviewQueue />} />
      </Routes>
    </MemoryRouter>,
  );

const page = (rows: ChangeProposal[], count = rows.length) => ({ count, next: null, previous: null, results: rows });
const withOpen = (rows: ChangeProposal[], settings = settingsOn, count = rows.length) => {
  api.getSettings.mockResolvedValue(settings);
  api.listOpen.mockResolvedValue(page(rows, count));
};

const cardEl = (p: ChangeProposal) => document.querySelector(`[data-proposal-id="${p.id}"]`) as HTMLElement;
const findCard = async (p: ChangeProposal) => {
  await waitFor(() => expect(cardEl(p)).not.toBeNull());
  return within(cardEl(p));
};
const key = (k: string) => fireEvent.keyDown(window, { key: k });
const dwell = () => act(() => new Promise((resolve) => setTimeout(resolve, 1700)));
/** Focus the card the way a reviewer does with j, and wait until the a key is armed. */
const focusAndArm = async (p: ChangeProposal) => {
  await findCard(p);
  act(() => cardEl(p).focus());
  await dwell();
};

beforeEach(() => {
  jest.resetAllMocks();
  resetReviewSettingsCache();
  try {
    localStorage.clear();
  } catch {
    // ignore
  }
  api.getContact.mockResolvedValue({ name: 'Pat Example', is_primary: false, contact_type: 'Other' });
  api.list.mockResolvedValue(page([]));
});

// ------------------------------------------------------------------ M1: keys respect what the card is doing

describe('keys follow the same rule as the buttons', () => {
  it('a does nothing while the card is being edited, even with focus back on the card', async () => {
    const p = makeProposal({ seen_version: 'v-m1' });
    withOpen([p]);
    renderPage();
    const card = await findCard(p);
    fireEvent.click(card.getByRole('button', { name: 'Edit' }));
    fireEvent.change(card.getByLabelText('Phone'), { target: { value: '+66 2 555 5555' } });
    await focusAndArm(p);
    key('a');
    key('x');
    key('r');
    expect(api.accept).not.toHaveBeenCalled();
    expect(api.acceptWithEdits).not.toHaveBeenCalled();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(card.getByLabelText('Phone')).toHaveValue('+66 2 555 5555');
  });

  it('a under a conflict, or with the changed-record box unticked, does not accept and says why', async () => {
    const other = makeProposal({ proposer_username: 'other-bot', patch: { phone: '+66 2 999 9999' } });
    const conflicted = makeProposal({
      conflicts_with: [
        {
          id: other.id,
          proposer_username: 'other-bot',
          patch: other.patch,
          evidence_occurred_at: null,
          created_at: '',
        },
      ],
    });
    const changed = makeProposal({
      target_changed_at: '2026-11-18T08:00:00Z',
      patch: { city: 'Krabi' },
      current_values: { city: 'Trang' },
    });
    withOpen([conflicted, other, changed]);
    renderPage('/review?tab=look');
    await focusAndArm(conflicted);
    key('a');
    // The card always shows the reason; the key adds the same reason as a message.
    await waitFor(() => expect(screen.getAllByText(/Choose which of the two suggestions/).length).toBe(2));
    await focusAndArm(changed);
    key('a');
    await waitFor(() => expect(screen.getAllByText(/Tick “I have compared the current values” first/).length).toBe(2));
    expect(api.accept).not.toHaveBeenCalled();
  });

  it('a held down sends one decision while the first is in flight', async () => {
    const p = makeProposal({ seen_version: 'v-held' });
    withOpen([p]);
    api.accept.mockReturnValue(new Promise(() => undefined));
    renderPage();
    await focusAndArm(p);
    key('a');
    key('a');
    key('a');
    expect(api.accept).toHaveBeenCalledTimes(1);
  });

  it('shortcuts can be switched off, and the choice is remembered', async () => {
    const p = makeProposal();
    withOpen([p]);
    const { unmount } = renderPage();
    await findCard(p);
    fireEvent.click(screen.getByLabelText('Keyboard shortcuts'));
    key('j');
    expect(document.activeElement).not.toBe(cardEl(p));
    unmount();
    renderPage();
    await findCard(p);
    expect(screen.getByLabelText('Keyboard shortcuts')).not.toBeChecked();
  });

  it('after a decision, focus moves to the next card', async () => {
    const a = makeProposal({ evidence_occurred_at: '2026-11-17T12:00:00Z' });
    const b = makeProposal({
      evidence_occurred_at: '2026-11-17T08:00:00Z',
      patch: { city: 'X' },
      current_values: { city: 'Y' },
    });
    withOpen([a, b]);
    api.accept.mockResolvedValue({ ...a, status: 'accepted', applied_patch: a.patch });
    renderPage();
    const card = await findCard(a);
    fireEvent.click(card.getByRole('button', { name: 'Accept' }));
    await waitFor(() => expect(document.activeElement).toBe(cardEl(b)));
  });

  it('says in visible text why Accept is disabled', async () => {
    const p = makeProposal({ target_changed_at: '2026-11-18T08:00:00Z' });
    withOpen([p]);
    renderPage('/review?tab=look');
    const card = await findCard(p);
    expect(card.getByTestId('accept-blocked-reason')).toHaveTextContent(
      'Tick “I have compared the current values” first.',
    );
  });
});

// ------------------------------------------------------------------ M2: the tick and the choice gate every accepting route

describe('every accepting route is gated', () => {
  it('Edit and the e key wait for the tick; accept with edits sends only after it', async () => {
    const p = makeProposal({ seen_version: 'v-c', target_changed_at: '2026-11-18T08:00:00Z' });
    withOpen([p]);
    api.acceptWithEdits.mockResolvedValue({ ...p, status: 'edited', applied_patch: { phone: '+66 2 555 5555' } });
    renderPage('/review?tab=look');
    const card = await findCard(p);
    expect(card.getByRole('button', { name: 'Edit' })).toBeDisabled();
    act(() => cardEl(p).focus());
    key('e');
    expect(card.queryByLabelText('Phone')).not.toBeInTheDocument();
    fireEvent.click(card.getByLabelText('I have compared the current values'));
    fireEvent.click(card.getByRole('button', { name: 'Edit' }));
    fireEvent.change(card.getByLabelText('Phone'), { target: { value: '+66 2 555 5555' } });
    fireEvent.click(card.getByRole('button', { name: 'Accept with edits' }));
    await waitFor(() => expect(api.acceptWithEdits).toHaveBeenCalledWith(p.id, 'v-c', { phone: '+66 2 555 5555' }, []));
  });

  it('a 409 record_changed while editing closes the form and asks for the tick again', async () => {
    const p = makeProposal({ seen_version: 'v1' });
    withOpen([p]);
    const fresh = {
      ...p,
      seen_version: 'v2',
      target_changed_at: '2026-11-18T09:00:00Z',
      current_values: { phone: '+66 2 777 0000' },
    };
    api.acceptWithEdits.mockRejectedValueOnce(
      new ReviewApiError(409, 'record_changed', 'changed', {
        code: 'record_changed',
        proposal: {
          id: p.id,
          seen_version: 'v2',
          status: 'proposed',
          patch: p.patch,
          current_values: fresh.current_values,
          expected_version: 'x',
          target_changed_at: fresh.target_changed_at,
        },
      }),
    );
    api.get.mockResolvedValue(fresh);
    renderPage();
    const card = await findCard(p);
    fireEvent.click(card.getByRole('button', { name: 'Edit' }));
    fireEvent.change(card.getByLabelText('Phone'), { target: { value: '+66 2 555 5555' } });
    fireEvent.click(card.getByRole('button', { name: 'Accept with edits' }));
    expect(await card.findByTestId('record-changed')).toBeInTheDocument();
    expect(card.queryByRole('button', { name: 'Accept with edits' })).not.toBeInTheDocument();
    expect(card.getByLabelText('I have compared the current values')).not.toBeChecked();
    expect(card.getByRole('button', { name: 'Edit' })).toBeDisabled();
    expect(api.acceptWithEdits).toHaveBeenCalledTimes(1);
  });

  it('the tick resets when the card is refreshed', async () => {
    const p = makeProposal({ seen_version: 'v1', target_changed_at: '2026-11-18T08:00:00Z' });
    withOpen([p]);
    api.reject.mockRejectedValueOnce(
      new ReviewApiError(409, 'stale_view', 'stale', {
        code: 'stale_view',
        proposal: {
          id: p.id,
          seen_version: 'v9',
          status: 'proposed',
          patch: p.patch,
          current_values: p.current_values,
          expected_version: 'z',
          target_changed_at: '2026-11-18T10:00:00Z',
        },
      }),
    );
    api.get.mockResolvedValue({ ...p, seen_version: 'v9', target_changed_at: '2026-11-18T10:00:00Z' });
    renderPage('/review?tab=look');
    const card = await findCard(p);
    fireEvent.click(card.getByLabelText('I have compared the current values'));
    expect(card.getByLabelText('I have compared the current values')).toBeChecked();
    fireEvent.click(card.getByRole('button', { name: 'Reject' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Wrong record' }));
    fireEvent.click(within(dialog).getByRole('button', { name: 'Reject' }));
    await waitFor(() => expect(api.get).toHaveBeenCalled());
    await waitFor(() =>
      expect(within(cardEl(p)).getByLabelText('I have compared the current values')).not.toBeChecked(),
    );
  });

  it('an email or phone change without captured evidence needs the source tick, also for edits', async () => {
    const p = makeProposal({ evidence: 'verified_agent_recorded', seen_version: 'v-s' });
    withOpen([p]);
    api.accept.mockResolvedValue({ ...p, status: 'accepted', applied_patch: p.patch });
    renderPage();
    const card = await findCard(p);
    expect(card.getByRole('button', { name: 'Accept' })).toBeDisabled();
    expect(card.getByRole('button', { name: 'Edit' })).toBeDisabled();
    expect(card.getByTestId('accept-blocked-reason')).toHaveTextContent('I checked this against the source myself');
    fireEvent.click(card.getByLabelText('I checked this against the source myself'));
    fireEvent.click(card.getByRole('button', { name: 'Accept' }));
    await waitFor(() => expect(api.accept).toHaveBeenCalledWith(p.id, 'v-s'));
  });
});

// ------------------------------------------------------------------ conflicts

describe('conflicts', () => {
  const pair = () => {
    const other = makeProposal({
      proposer_username: 'other-bot',
      seen_version: 'vo',
      patch: { email: 'b@example.com' },
      evidence_quote: 'write to b@example.com',
    });
    const p = makeProposal({ seen_version: 'vp', patch: { email: 'a@example.com' } });
    p.conflicts_with = [
      {
        id: other.id,
        proposer_username: 'other-bot',
        patch: { email: 'b@example.com' },
        evidence_occurred_at: null,
        created_at: '',
      },
    ];
    other.conflicts_with = [
      {
        id: p.id,
        proposer_username: p.proposer_username,
        patch: { email: 'a@example.com' },
        evidence_occurred_at: null,
        created_at: '',
      },
    ];
    return { p, other };
  };

  it('shows the other suggestion’s evidence before it can be rejected', async () => {
    const { p, other } = pair();
    withOpen([p, other]);
    renderPage('/review?tab=look');
    const card = await findCard(p);
    expect(within(card.getByTestId('conflict')).getByText('write to b@example.com')).toBeInTheDocument();
  });

  it('reads the other suggestion when it is not loaded, and blocks accepting until its evidence shows', async () => {
    const { p, other } = pair();
    withOpen([p]);
    let deliver: (v: ChangeProposal) => void = () => undefined;
    api.get.mockReturnValue(new Promise((resolve) => (deliver = resolve)));
    renderPage('/review?tab=look');
    const card = await findCard(p);
    await waitFor(() => expect(api.get).toHaveBeenCalledWith(other.id));
    expect(card.getByText('Loading its evidence…')).toBeInTheDocument();
    expect(card.getByRole('button', { name: 'Keep the other one' })).toBeDisabled();
    expect(card.getByTestId('accept-blocked-reason')).toHaveTextContent('evidence is shown');
    await act(async () => deliver(other));
    expect(await card.findByText('write to b@example.com')).toBeInTheDocument();
  });

  it('does not auto-reject the other when its values no longer match what was shown', async () => {
    const { p, other } = pair();
    const changedOther = { ...other, patch: { email: 'c@example.com' } };
    withOpen([p, changedOther]);
    api.get.mockResolvedValue(changedOther);
    api.accept.mockResolvedValue({ ...p, status: 'accepted', applied_patch: p.patch });
    renderPage('/review?tab=look');
    const card = await findCard(p);
    fireEvent.click(card.getByRole('button', { name: 'Keep this one' }));
    fireEvent.click(card.getByRole('button', { name: 'Accept and reject the other' }));
    expect(await screen.findByText(/could not be matched to what was shown and is still open/)).toBeInTheDocument();
    expect(api.reject).not.toHaveBeenCalled();
  });
});

// ------------------------------------------------------------------ M3: bulk reject sends exactly what the dialog lists

describe('bulk reject', () => {
  it('a filter change clears the selection, and the dialog lists exactly what will be sent', async () => {
    const a = makeProposal({ company_id: 'ca', company_name: 'Alpha Inn', batch_key: 'b-a' });
    const a2 = makeProposal({
      company_id: 'ca',
      company_name: 'Alpha Inn',
      batch_key: 'b-a',
      patch: { city: 'X' },
      current_values: { city: 'Y' },
    });
    const b = makeProposal({ company_id: 'cb', company_name: 'Beta Lodge' });
    withOpen([a, a2, b]);
    api.bulkReject.mockResolvedValue({ rejected: [a.id, a2.id], skipped: [], not_found: [] });
    renderPage();
    await findCard(b);
    fireEvent.click(within(cardEl(b)).getByLabelText('Select for rejecting together'));
    fireEvent.click(screen.getByLabelText('Select the batch to reject it'));
    expect(screen.getByTestId('bulk-bar')).toHaveTextContent('3 selected');
    // Filtering to one company clears the selection instead of keeping hidden cards selected.
    fireEvent.mouseDown(screen.getByLabelText('Company'));
    fireEvent.click(within(screen.getByRole('listbox')).getByText('Alpha Inn'));
    await waitFor(() => expect(screen.queryByTestId('bulk-bar')).not.toBeInTheDocument());
    fireEvent.click(screen.getByLabelText('Select the batch to reject it'));
    fireEvent.click(within(screen.getByTestId('bulk-bar')).getByRole('button', { name: 'Reject selected…' }));
    const dialog = await screen.findByRole('dialog');
    const list = within(dialog).getByTestId('bulk-list');
    expect(list).toHaveTextContent('Alpha Inn: Update fields (Phone)');
    expect(list).toHaveTextContent('Alpha Inn: Update fields (City)');
    expect(list).not.toHaveTextContent('Beta Lodge');
    fireEvent.change(within(dialog).getByLabelText('Reason'), { target: { value: 'Not worth recording' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Reject 2' }));
    await waitFor(() => expect(api.bulkReject).toHaveBeenCalledTimes(1));
    expect(api.bulkReject.mock.calls[0][0].map((i) => i.id).sort()).toEqual([a.id, a2.id].sort());
  });

  it('refuses more than 200 in the page, with the reason', async () => {
    const rows = Array.from({ length: 201 }, (_, i) =>
      makeProposal({ batch_key: 'big-batch', patch: { city: `City ${i}` }, current_values: { city: 'Old' } }),
    );
    withOpen(rows);
    renderPage();
    await findCard(rows[0]);
    for (let i = 0; i < 4; i += 1) fireEvent.click(screen.getByTestId('show-more-cards'));
    fireEvent.click(screen.getByLabelText('Select the batch to reject it'));
    expect(screen.getByTestId('bulk-bar')).toHaveTextContent('201 selected');
    expect(screen.getByRole('button', { name: 'Reject selected…' })).toBeDisabled();
    expect(screen.getByTestId('bulk-note')).toHaveTextContent('At most 200 can be rejected at once');
  }, 60000);
});

// ------------------------------------------------------------------ M4: volume

describe('a long queue', () => {
  it('renders 50 cards at a time and says when more exist than are loaded', async () => {
    const rows = Array.from({ length: 120 }, (_, i) =>
      makeProposal({ patch: { city: `C${i}` }, current_values: { city: 'Old' } }),
    );
    withOpen(rows, settingsOn, 1007);
    api.listOpen.mockResolvedValueOnce(page(rows, 1007)).mockResolvedValueOnce(page([makeProposal()], 1007));
    renderPage();
    await findCard(rows[0]);
    expect(screen.getAllByTestId('proposal-card')).toHaveLength(50);
    expect(screen.getByTestId('more-not-loaded')).toHaveTextContent('Showing the newest 120 of 1,007 open suggestions');
    fireEvent.click(screen.getByTestId('show-more-cards'));
    expect(screen.getAllByTestId('proposal-card')).toHaveLength(100);
    fireEvent.click(within(screen.getByTestId('more-not-loaded')).getByRole('button', { name: /Load 200 more/ }));
    await waitFor(() => expect(api.listOpen).toHaveBeenLastCalledWith(2, 'newest'));
  }, 30000);

  it('looks up contacts only for rendered cards, at most four at a time', async () => {
    const rows = Array.from({ length: 80 }, (_, i) =>
      makeProposal({
        target_collection: 'contact',
        target_id: `k-${i}`,
        patch: { title: `T${i}` },
        current_values: { title: 'Old' },
      }),
    );
    withOpen(rows);
    let inFlight = 0;
    let peak = 0;
    api.getContact.mockImplementation(async () => {
      inFlight += 1;
      peak = Math.max(peak, inFlight);
      await new Promise((resolve) => setTimeout(resolve, 5));
      inFlight -= 1;
      return { name: 'Someone' };
    });
    renderPage();
    await findCard(rows[0]);
    await waitFor(() => expect(api.getContact).toHaveBeenCalledTimes(50), { timeout: 5000 });
    expect(peak).toBeLessThanOrEqual(4);
  }, 30000);

  it('can order by soonest expiry', async () => {
    withOpen([]);
    renderPage('/review?sort=expiring');
    await waitFor(() => expect(api.listOpen).toHaveBeenCalledWith(1, 'expiring'));
  });
});

// ------------------------------------------------------------------ M5, L3, L4, L5: what is shown is what is stored

describe('faithful display', () => {
  it('prints where the source link goes, and refuses an unusual address', async () => {
    const good = makeProposal({ evidence_source_url: 'https://mail.google.com/mail/u/0/#inbox/1' });
    const bad = makeProposal({
      evidence_source_url: 'https://mail.google.com@phish.example/login',
      patch: { city: 'X' },
      current_values: { city: 'Y' },
    });
    withOpen([good, bad]);
    renderPage();
    const g = await findCard(good);
    expect(g.getByRole('link', { name: /Open in Gmail/ })).toHaveAttribute(
      'href',
      'https://mail.google.com/mail/u/0/#inbox/1',
    );
    expect(g.getByTestId('source-host')).toHaveTextContent('mail.google.com');
    expect(within(g.getByTestId('source-host')).getByText('google.com').tagName).toBe('STRONG');
    const b = within(cardEl(bad));
    expect(b.queryByRole('link', { name: /Open in Gmail|Open link/ })).toBeNull();
    expect(b.getByTestId('source-link-refused')).toHaveTextContent('Link not shown: unusual address');
  });

  it('keeps runs of spaces, marks unusual and edge spaces, and says so', async () => {
    const p = makeProposal({ patch: { city: ' Bangkok\u00A0Noi' }, current_values: { city: 'Bangkok  Noi' } });
    withOpen([p]);
    renderPage();
    const card = await findCard(p);
    expect(card.getByTestId('before-city').textContent).toBe('Bangkok  Noi');
    const after = card.getByTestId('after-city');
    expect(after.querySelector('[data-hidden-char="U+00A0"]')).not.toBeNull();
    expect(after.querySelector('[data-hidden-char="\u2423"]')).not.toBeNull();
    expect(card.getAllByText('Contains unusual spaces').length).toBeGreaterThan(0);
  });

  it('marks tag characters in quotes, and tells writing directions from look-alike letters', async () => {
    const tag = String.fromCodePoint(0xe0041);
    const p = makeProposal({
      kind: 'new_contact',
      target_collection: 'contact',
      target_id: '',
      evidence: 'verified_captured',
      evidence_quote: `Title is Manager${tag}`,
      patch: { name: 'Dana Example', email: 'dana@example.com', title: '\u05DE\u05E0\u05D4\u05DC 123 Manager' },
      current_values: {},
      proposer_username: 'reviewer.\u043Ene',
    });
    withOpen([p]);
    renderPage();
    const card = await findCard(p);
    expect(card.getByTestId('evidence-quote').querySelector('[data-hidden-char="U+E0041"]')).not.toBeNull();
    expect(card.getByText('Mixed writing directions')).toBeInTheDocument();
    // The look-alike proposer name (a Cyrillic o) is flagged where it is shown.
    expect(card.getAllByText('Look-alike letters').length).toBe(1);
    expect(cardEl(p).querySelectorAll('bdi').length).toBeGreaterThan(3);
  });

  it('labels the old values "When suggested" until the API re-reads them', async () => {
    const plain = makeProposal();
    const reread = makeProposal({
      target_changed_at: '2026-11-18T08:00:00Z',
      patch: { city: 'X' },
      current_values: { city: 'Y' },
    });
    withOpen([plain, reread]);
    renderPage();
    expect((await findCard(plain)).getByTestId('before-header')).toHaveTextContent('When suggested');
    fireEvent.click(screen.getByRole('tab', { name: /Needs another look/ }));
    expect((await findCard(reread)).getByTestId('before-header')).toHaveTextContent('Now');
  });

  it('says "Now" when the backend keeps current values fresh', async () => {
    const p = makeProposal();
    withOpen([p], { ...settingsOn, you_can_review: true });
    renderPage();
    expect((await findCard(p)).getByTestId('before-header')).toHaveTextContent('Now');
  });

  it('shows the proposer kind as sent and the evidence badge styles', async () => {
    const ai = makeProposal({
      proposer_kind: 'ai',
      evidence: 'verified_agent_recorded',
      patch: { city: 'X' },
      current_values: { city: 'Y' },
    });
    const captured = makeProposal({ proposer_kind: 'job' });
    withOpen([ai, captured]);
    renderPage();
    expect((await findCard(ai)).getByTestId('proposer-kind')).toHaveTextContent('(AI)');
    expect(within(cardEl(captured)).getByTestId('proposer-kind')).toHaveTextContent('(Job)');
    const agentBadge = document.querySelector('[data-evidence="verified_agent_recorded"]')!;
    const capturedBadge = document.querySelector('[data-evidence="verified_captured"]')!;
    expect(agentBadge.className).toMatch(/MuiChip-outlined/);
    expect(agentBadge.className).not.toMatch(/colorSuccess/);
    expect(capturedBadge.className).toMatch(/MuiChip-filled/);
    expect(capturedBadge.className).toMatch(/colorSuccess/);
  });
});

// ------------------------------------------------------------------ L8

describe('Decided tab', () => {
  it('says the evidence filter applies to loaded rows', async () => {
    const rows = [
      makeProposal({ status: 'accepted', evidence: 'unverified' }),
      makeProposal({ status: 'rejected', evidence: 'verified_captured' }),
    ];
    withOpen([]);
    api.list.mockResolvedValue(page(rows, 40));
    renderPage('/review?tab=decided&evidence=unverified');
    expect(await screen.findByTestId('decided-count')).toHaveTextContent(
      '1 of the 2 loaded match the evidence filter (40 decided in all',
    );
    expect(screen.getByRole('button', { name: /Load 25 more \(38 not loaded\)/ })).toBeInTheDocument();
  });
});
