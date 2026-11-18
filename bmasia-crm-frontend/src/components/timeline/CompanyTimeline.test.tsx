import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import CompanyTimeline from './CompanyTimeline';
import ApiService from '../../services/api';
import { TimelineEvent, TimelinePage } from './timelineModel';

jest.mock('../../services/api', () => ({
  __esModule: true,
  default: { getCompanyTimeline: jest.fn() },
}));

const api = ApiService as unknown as { getCompanyTimeline: jest.Mock };

const now = new Date();
const hoursAgo = (h: number) => new Date(now.getTime() - h * 3600 * 1000).toISOString();

const ev = (overrides: Partial<TimelineEvent>): TimelineEvent => ({
  id: 'note:1',
  type: 'note',
  category: 'note',
  occurred_at: hoursAgo(1),
  precision: 'datetime',
  title: 'Event',
  detail: '',
  actor: null,
  links: [],
  changes: [],
  extra: {},
  ...overrides,
});

const page = (results: TimelineEvent[], more = false, extra: Partial<TimelinePage> = {}): TimelinePage => ({
  results,
  next_cursor: more ? 'CURSOR-2' : null,
  has_more: more,
  categories: [],
  facets: {
    types: { note: 2, task: 0, email: 1, care: 0, quote: 0, contract: 1, invoice: 0, opportunity: 0, ticket: 0, change: 1 },
    actors: [{ id: 'u-1', name: 'Alex Demo', kind: 'user', count: 2 }],
  },
  ...extra,
});

const FIRST = [
  ev({
    id: 'note:1',
    title: 'Renewal call',
    detail: 'GM wants two more zones.',
    actor: { id: 'u-1', name: 'Alex Demo', kind: 'user' },
    extra: { note_type: 'Call' },
    links: [{ type: 'contact', id: 'p-1', label: 'Mai Tan' }],
  }),
  ev({
    id: 'audit_change:2',
    type: 'field_change',
    category: 'change',
    occurred_at: hoursAgo(2),
    title: 'TH-CT26001 updated: end date',
    actor: { id: 'u-9', name: 'Cira', kind: 'agent' },
    links: [{ type: 'contract', id: 'c-1', label: 'TH-CT26001' }],
    changes: [{ field: 'end_date', label: 'End date', kind: 'date', old: '2026-12-31', new: '2027-12-31' }],
  }),
  ev({
    id: 'contract_signed:3',
    type: 'contract_signed',
    category: 'contract',
    precision: 'date',
    date: '2026-01-05',
    occurred_at: '2026-01-04T17:00:00+00:00',
    title: 'Contract TH-CT26001 signed',
    extra: { money: { amount: '108000.00', currency: 'THB' } },
    links: [{ type: 'contract', id: 'c-1', label: 'TH-CT26001' }],
  }),
];

const renderTimeline = (props: Partial<React.ComponentProps<typeof CompanyTimeline>> = {}) =>
  render(
    <MemoryRouter>
      <CompanyTimeline companyId="co-1" {...props} />
    </MemoryRouter>
  );

beforeEach(() => {
  jest.clearAllMocks();
  api.getCompanyTimeline.mockResolvedValue(page(FIRST, true));
});

it('shows a day-grouped feed with icons, actors, amounts and links', async () => {
  const onOpenContact = jest.fn();
  renderTimeline({ onOpenContact });
  expect(await screen.findByText('Renewal call')).toBeInTheDocument();
  expect(api.getCompanyTimeline).toHaveBeenCalledWith('co-1', expect.objectContaining({ facets: true, page_size: 25 }));

  expect(screen.getByText('5 Jan 2026')).toBeInTheDocument(); // date-only event keeps its day
  expect(screen.getByText('Date only')).toBeInTheDocument();
  expect(screen.getByText('THB 108,000')).toBeInTheDocument();
  expect(screen.getByText('Cira')).toBeInTheDocument();
  expect(screen.getByText('(agent)')).toBeInTheDocument();
  expect(screen.getAllByRole('link', { name: 'Open contract TH-CT26001' })[0]).toHaveAttribute('href', '/contracts/c-1');

  fireEvent.click(screen.getByRole('button', { name: 'Open contact Mai Tan' }));
  expect(onOpenContact).toHaveBeenCalledWith('p-1');
});

it('expands an event to show its detail and field changes as sentences', async () => {
  renderTimeline();
  await screen.findByText('Renewal call');
  const toggle = screen.getByRole('button', { name: 'Show 1 change' });
  expect(toggle).toHaveAttribute('aria-expanded', 'false');
  fireEvent.click(toggle);
  expect(await screen.findByText('Changed End date from 31 Dec 2026 to 31 Dec 2027')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Hide details' })).toHaveAttribute('aria-expanded', 'true');

  fireEvent.click(screen.getByRole('button', { name: 'Show details' }));
  expect(await screen.findByText('GM wants two more zones.')).toBeInTheDocument();
});

it('filters by type with chips that carry counts', async () => {
  renderTimeline();
  await screen.findByText('Renewal call');
  const chips = screen.getByRole('group', { name: 'Filter by type' });
  expect(within(chips).getByText('Notes')).toBeInTheDocument();
  expect(within(chips).queryByText('Tasks')).not.toBeInTheDocument(); // zero counts are hidden

  fireEvent.click(within(chips).getByText('Emails'));
  await waitFor(() =>
    expect(api.getCompanyTimeline).toHaveBeenLastCalledWith('co-1', expect.objectContaining({ types: ['email'] }))
  );
  fireEvent.click(within(chips).getByText('All'));
  await waitFor(() =>
    expect(api.getCompanyTimeline).toHaveBeenLastCalledWith('co-1', expect.objectContaining({ types: undefined }))
  );
});

it('searches after typing stops', async () => {
  renderTimeline();
  await screen.findByText('Renewal call');
  fireEvent.change(screen.getByRole('textbox', { name: 'Search activity' }), { target: { value: 'zones' } });
  await waitFor(() =>
    expect(api.getCompanyTimeline).toHaveBeenLastCalledWith('co-1', expect.objectContaining({ q: 'zones' }))
  );
});

it('loads more with the cursor and appends without duplicates', async () => {
  api.getCompanyTimeline
    .mockResolvedValueOnce(page(FIRST, true))
    .mockResolvedValueOnce(page([FIRST[2], ev({ id: 'email:9', category: 'email', type: 'email_sent', title: 'Email sent: Hello', occurred_at: '2025-05-01T03:00:00+00:00' })], false));
  renderTimeline();
  await screen.findByText('Renewal call');
  fireEvent.click(screen.getByRole('button', { name: 'Load more' }));
  expect(await screen.findByText('Email sent: Hello')).toBeInTheDocument();
  expect(api.getCompanyTimeline).toHaveBeenLastCalledWith('co-1', expect.objectContaining({ cursor: 'CURSOR-2' }));
  expect(screen.getAllByText('Contract TH-CT26001 signed')).toHaveLength(1);
  expect(screen.queryByRole('button', { name: 'Load more' })).not.toBeInTheDocument();
});

it('says so when there is no activity yet', async () => {
  api.getCompanyTimeline.mockResolvedValue(page([], false));
  renderTimeline();
  expect(await screen.findByText('No activity yet')).toBeInTheDocument();
});

it('shows an error with a way to try again', async () => {
  api.getCompanyTimeline.mockRejectedValueOnce(new Error('boom')).mockResolvedValueOnce(page(FIRST, false));
  renderTimeline();
  expect(await screen.findByText('Could not load the activity.')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
  expect(await screen.findByText('Renewal call')).toBeInTheDocument();
});

it('for one record: asks for that record and does not link back to it', async () => {
  renderTimeline({ record: { type: 'contract', id: 'c-1' }, showFilters: false });
  await screen.findByText('Renewal call');
  expect(api.getCompanyTimeline).toHaveBeenCalledWith(
    'co-1',
    expect.objectContaining({ record: { type: 'contract', id: 'c-1' }, facets: false })
  );
  expect(screen.queryByRole('link', { name: 'Open contract TH-CT26001' })).not.toBeInTheDocument();
  expect(screen.queryByRole('textbox', { name: 'Search activity' })).not.toBeInTheDocument();
});
