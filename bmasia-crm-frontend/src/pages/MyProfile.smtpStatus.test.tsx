import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import MyProfile from './MyProfile';
import ApiService from '../services/api';

jest.mock('../services/api', () => ({
  __esModule: true,
  default: { getMyProfile: jest.fn() },
}));

const api = ApiService as unknown as { getMyProfile: jest.Mock };

const profile = (over: Record<string, unknown>) => ({
  id: 'u-1', username: 'fixture', email: 'fixture@example.com', first_name: 'Fixture', last_name: 'User',
  role: 'Sales', is_active: true, date_joined: '2026-01-01T00:00:00Z', smtp_email: 'fixture@example.com',
  ...over,
});

const renderPage = () =>
  render(
    <MemoryRouter>
      <MyProfile />
    </MemoryRouter>
  );

it('says the saved mail password needs re-entering when the server cannot read it', async () => {
  api.getMyProfile.mockResolvedValue(
    profile({ smtp_configured: false, smtp_status: 'Set (unreadable: needs re-entry)' })
  );
  renderPage();
  expect(await screen.findByText('Needs re-entry: your saved password cannot be read')).toBeInTheDocument();
  expect(screen.queryByText('Not Configured')).not.toBeInTheDocument();
});

it('keeps the usual chips otherwise', async () => {
  api.getMyProfile.mockResolvedValue(profile({ smtp_configured: true, smtp_status: 'Set' }));
  renderPage();
  expect(await screen.findByText('Configured')).toBeInTheDocument();
  expect(screen.queryByText(/Needs re-entry/)).not.toBeInTheDocument();
});
