import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import NeedsFixingCard from './NeedsFixingCard';
import { getDataQualitySummary } from '../services/dataQuality';

jest.mock('../services/authService', () => ({ __esModule: true, default: {}, authApi: {} }));
jest.mock('../services/dataQuality', () => {
  const actual = jest.requireActual('../services/dataQuality');
  return { ...actual, getDataQualitySummary: jest.fn() };
});

const summary = jest.mocked(getDataQualitySummary);

const check = (key: string, title: string, severity: 'high' | 'medium' | 'low', count: number) => ({
  key,
  title,
  why: `Why ${title}`,
  severity,
  record_type: 'contract' as const,
  count,
  rows: [],
});

const response = (checks: ReturnType<typeof check>[]) => ({
  today: '2026-11-19',
  generated_at: '2026-11-18T18:30:00Z',
  checks,
  total: checks.reduce((n, c) => n + c.count, 0),
  clear: checks.filter((c) => c.count === 0).length,
});

const renderCard = () =>
  render(
    <MemoryRouter>
      <NeedsFixingCard />
    </MemoryRouter>
  );

beforeEach(() => summary.mockReset());

it('lists checks with records in the server order, each linking to its list', async () => {
  summary.mockResolvedValue(
    response([
      check('contract_active_past_end', 'Active contracts past their end date', 'high', 121),
      check('contract_ending_no_successor', 'Contracts ending within 60 days with no renewal', 'high', 63),
      check('task_overdue', 'Overdue tasks', 'medium', 4),
      check('invoice_overdue', 'Overdue invoices', 'high', 0),
      check('quote_sent_expired', 'Sent quotes that expired without an answer', 'medium', 0),
    ])
  );
  renderCard();
  expect(screen.getByLabelText('Loading checks')).toBeInTheDocument();
  const first = await screen.findByRole('link', { name: /Active contracts past their end date/ });
  expect(first).toHaveAttribute('href', '/needs-fixing/contract_active_past_end');
  expect(within(first).getByText('121')).toBeInTheDocument();
  expect(within(screen.getByRole('region', { name: 'High priority' })).getAllByRole('link')).toHaveLength(2);
  expect(within(screen.getByRole('region', { name: 'Medium priority' })).getByRole('link')).toHaveAttribute('href', '/needs-fixing/task_overdue');
  const lines = screen.getAllByRole('link').filter((a) => a.getAttribute('href')?.startsWith('/needs-fixing/'));
  expect(lines.map((a) => a.getAttribute('href'))).toEqual([
    '/needs-fixing/contract_active_past_end',
    '/needs-fixing/contract_ending_no_successor',
    '/needs-fixing/task_overdue',
  ]);
  expect(screen.getByRole('link', { name: 'View all' })).toHaveAttribute('href', '/needs-fixing');
  expect(summary).toHaveBeenCalledWith(0);
});

it('folds checks with nothing to fix into one line that opens', async () => {
  summary.mockResolvedValue(
    response([
      check('task_overdue', 'Overdue tasks', 'medium', 2),
      check('invoice_overdue', 'Overdue invoices', 'high', 0),
      check('quote_sent_expired', 'Sent quotes that expired without an answer', 'medium', 0),
    ])
  );
  renderCard();
  const toggle = await screen.findByRole('button', { name: /2 checks clear/ });
  expect(screen.queryByText('Overdue invoices')).toBeNull();
  expect(toggle).toHaveAttribute('aria-expanded', 'false');
  fireEvent.click(toggle);
  expect(toggle).toHaveAttribute('aria-expanded', 'true');
  expect(screen.getByText('Overdue invoices')).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: /Overdue invoices/ })).toBeNull();
});

it('says so when every check is clear', async () => {
  summary.mockResolvedValue(response([check('task_overdue', 'Overdue tasks', 'medium', 0)]));
  renderCard();
  expect(await screen.findByText('Nothing needs fixing: all 1 checks are clear.')).toBeInTheDocument();
});

it('shows an error with a retry', async () => {
  summary.mockRejectedValueOnce(new Error('Network Error'));
  summary.mockResolvedValueOnce(response([check('task_overdue', 'Overdue tasks', 'medium', 3)]));
  renderCard();
  expect(await screen.findByText('Network Error')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
  expect(await screen.findByRole('link', { name: /Overdue tasks/ })).toBeInTheDocument();
  expect(summary).toHaveBeenCalledTimes(2);
});
