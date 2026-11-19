import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ReviewQueue from './ReviewQueue';
import reviewApi from '../../services/reviewApi';
import { makeProposal, settingsOn } from './testFixtures';
import { resetReviewSettingsCache } from './useReviewStatus';

// The page's own accept check, on its own: the card is replaced by a stub whose button always asks to accept,
// so nothing but the page stands between the click and the API.
jest.mock('./ProposalCard', () => {
  const ReactLib = jest.requireActual('react');
  return {
    __esModule: true,
    default: (props: any) =>
      ReactLib.createElement(
        'button',
        { onClick: () => props.handlers.onAccept(props.proposal), 'data-testid': `force-${props.proposal.id}` },
        'force accept',
      ),
  };
});
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
      getContact: jest.fn(),
    },
  };
});

const api = reviewApi as jest.Mocked<typeof reviewApi>;
const page = (rows: any[]) => ({ count: rows.length, next: null, previous: null, results: rows });

beforeEach(() => {
  jest.resetAllMocks();
  resetReviewSettingsCache();
  api.getSettings.mockResolvedValue(settingsOn);
  api.list.mockResolvedValue(page([]));
  api.accept.mockImplementation(async (id) => ({ ...makeProposal({ id }), status: 'accepted' }));
});

const renderPage = (entry: string) =>
  render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/review" element={<ReviewQueue />} />
      </Routes>
    </MemoryRouter>,
  );

it.each([
  ['an unticked changed record', { target_changed_at: '2026-11-18T08:00:00Z' }, '/review?tab=look'],
  [
    'an unpicked conflict',
    { conflicts_with: [{ id: 'x', proposer_username: 'o', patch: {}, evidence_occurred_at: null, created_at: '' }] },
    '/review?tab=look',
  ],
  ['an unticked source check', { evidence: 'unverified' as const, patch: { phone: '+66 2 000 0000' } }, '/review'],
  ['a read-only card', { proposer_username: 'reviewer.one' }, '/review'],
  ['an expired card', { expires_at: '2020-01-01T00:00:00Z' }, '/review'],
])('refuses to send an accept for %s', async (_name, overrides, entry) => {
  const p = makeProposal(overrides as any);
  api.listOpen.mockResolvedValue(page([p]));
  renderPage(entry);
  fireEvent.click(await screen.findByTestId(`force-${p.id}`));
  await act(() => new Promise((resolve) => setTimeout(resolve, 20)));
  expect(api.accept).not.toHaveBeenCalled();
});

it('sends an accept that the rule allows', async () => {
  const p = makeProposal({ seen_version: 'v-ok' });
  api.listOpen.mockResolvedValue(page([p]));
  renderPage('/review');
  fireEvent.click(await screen.findByTestId(`force-${p.id}`));
  await waitFor(() => expect(api.accept).toHaveBeenCalledWith(p.id, 'v-ok'));
  await act(() => new Promise((resolve) => setTimeout(resolve, 20)));
});
