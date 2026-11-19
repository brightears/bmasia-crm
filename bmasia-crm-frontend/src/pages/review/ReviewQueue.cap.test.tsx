/* eslint-disable testing-library/no-node-access, testing-library/prefer-screen-queries -- queries inside one card. */
import React from 'react';
import { fireEvent, render, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ReviewQueue from './ReviewQueue';
import reviewApi, { ChangeProposal } from '../../services/reviewApi';
import { makeProposal, settingsOn } from './testFixtures';
import { resetReviewSettingsCache } from './useReviewStatus';

// The look-up limit, made small so the "over the limit" path can be reached with a few cards.
jest.mock('./reviewModel', () => ({ ...jest.requireActual('./reviewModel'), LOOKUP_CAP: 2 }));
jest.mock('../../services/authService', () => ({ __esModule: true, default: {}, authApi: {} }));
jest.mock('../../contexts/AuthContext', () => ({ useAuth: () => ({ user: { username: 'reviewer.one' } }) }));
jest.mock('../../services/reviewApi', () => {
  const actual = jest.requireActual('../../services/reviewApi');
  return {
    __esModule: true,
    ...actual,
    default: { getSettings: jest.fn(), listOpen: jest.fn(), list: jest.fn(), get: jest.fn(), getContact: jest.fn() },
  };
});

const api = reviewApi as jest.Mocked<typeof reviewApi>;
const cardEl = (p: ChangeProposal) => document.querySelector(`[data-proposal-id="${p.id}"]`) as HTMLElement;

it('a contact look-up over the limit is marked as not checked and needs the tick', async () => {
  const rows = [0, 1, 2].map((i) =>
    makeProposal({
      target_collection: 'contact',
      target_id: `k-${i}`,
      patch: { title: `T${i}` },
      current_values: { title: 'Old' },
      evidence_occurred_at: `2026-11-1${7 - i}T09:00:00Z`,
    }),
  );
  api.getSettings.mockResolvedValue(settingsOn);
  api.list.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  api.listOpen.mockResolvedValue({ count: 3, next: null, previous: null, results: rows });
  api.getContact.mockResolvedValue({ name: 'Someone', is_primary: false });
  render(
    <MemoryRouter initialEntries={['/review']}>
      <Routes>
        <Route path="/review" element={<ReviewQueue />} />
      </Routes>
    </MemoryRouter>,
  );
  await waitFor(() => expect(api.getContact).toHaveBeenCalledTimes(2));
  const third = rows.find((r) => !api.getContact.mock.calls.some(([id]) => id === r.target_id))!;
  const card = within(cardEl(third));
  expect(await card.findByTestId('contact-unchecked')).toHaveTextContent(
    'Could not check whether this is the primary or billing contact',
  );
  expect(card.getByRole('button', { name: 'Accept' })).toBeDisabled();
  fireEvent.click(card.getByLabelText('I have checked this contact myself'));
  expect(card.getByRole('button', { name: 'Accept' })).toBeEnabled();
  expect(api.getContact).toHaveBeenCalledTimes(2);
});
