import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import Contacts from './Contacts';
import ApiService from '../services/api';

jest.mock('react-quill-new', () => ({ __esModule: true, default: () => null }));
jest.mock('../services/authService', () => ({ __esModule: true, default: { getCurrentUser: () => null, isAuthenticated: () => true } }));
jest.mock('../services/api', () => {
  const calls: Record<string, any> = {
    getContacts: jest.fn(),
    deleteContact: jest.fn(),
    getCompaniesSimple: () => Promise.resolve([{ id: 'a1b2c3d4-0000-0000-0000-000000000001', name: 'Fixture Resort' }]),
  };
  return {
    __esModule: true,
    default: new Proxy(calls, {
      get: (target, key) => (key in target ? target[key as string] : () => new Promise(() => {})),
    }),
  };
});

const api = ApiService as any;
const CO = 'a1b2c3d4-0000-0000-0000-000000000001';
const contact = {
  id: 'c-1',
  name: 'Alex Fixture',
  email: 'alex@fixture.example',
  phone: '+66 0000 0000',
  title: 'General Manager',
  department: 'Operations',
  company: CO,
  company_name: 'Fixture Resort',
  contact_type: 'Decision Maker',
  is_active: true,
  linkedin_url: 'https://linkedin.example/alex',
};

let lastLocation: any = null;
const Where: React.FC = () => {
  lastLocation = useLocation();
  return null;
};

const renderAt = (url: string) =>
  render(
    <MemoryRouter initialEntries={[url]}>
      <Where />
      <Routes>
        <Route path="/contacts" element={<Contacts />} />
        <Route path="/companies/:id" element={<div>company page</div>} />
      </Routes>
    </MemoryRouter>
  );

beforeEach(() => {
  api.getContacts.mockReset();
  api.getContacts.mockResolvedValue({ results: [contact], count: 60 });
});

it('reads search, company, status, sort and page from the address', async () => {
  renderAt(`/contacts?q=alex&company=${CO}&status=Inactive&sort=-created_at&page=2&size=50`);
  await waitFor(() => expect(api.getContacts).toHaveBeenCalled());
  expect(api.getContacts).toHaveBeenLastCalledWith({
    page: 2,
    page_size: 50,
    search: 'alex',
    company: CO,
    is_active: false,
    ordering: '-created_at',
  });
});

it('unknown values in the address fall back to the defaults and are not sent', async () => {
  renderAt('/contacts?company=not-an-id&status=Bogus&sort=password&size=-5');
  await waitFor(() => expect(api.getContacts).toHaveBeenCalled());
  expect(api.getContacts).toHaveBeenLastCalledWith({
    page: 1,
    page_size: 25,
    search: undefined,
    company: undefined,
    is_active: undefined,
    ordering: 'name',
  });
});

it('typing a search updates the address and goes back to page 1', async () => {
  renderAt('/contacts?status=Active&page=3');
  fireEvent.change(await screen.findByPlaceholderText(/search by name/i), { target: { value: 'alex' } });
  await waitFor(() => expect(lastLocation.search).toContain('q=alex'));
  expect(lastLocation.search).toContain('status=Active');
  expect(lastLocation.search).not.toContain('page=');
});

it('the email and LinkedIn buttons do not also open the contact panel', async () => {
  const open = jest.spyOn(window, 'open').mockImplementation(() => null);
  renderAt('/contacts');
  fireEvent.click(await screen.findByRole('button', { name: /send email to alex fixture/i }));
  fireEvent.click(screen.getByRole('button', { name: /linkedin profile of alex fixture/i }));
  expect(open).toHaveBeenCalledWith('mailto:alex@fixture.example', '_blank');
  expect(open).toHaveBeenCalledWith('https://linkedin.example/alex', '_blank');
  expect(screen.queryByRole('dialog')).toBeNull();
  open.mockRestore();
});

it('the more-actions menu keeps View, Edit, Send Email and Delete', async () => {
  renderAt('/contacts');
  fireEvent.click(await screen.findByRole('button', { name: /more actions for alex fixture/i }));
  const menu = await screen.findByRole('menu');
  ['View Details', 'Edit Contact', 'Send Email', 'Delete Contact'].forEach((label) =>
    expect(within(menu).getByText(label)).toBeInTheDocument()
  );
});

it('the company name links to the company page', async () => {
  renderAt('/contacts');
  fireEvent.click(await screen.findByRole('link', { name: 'Fixture Resort' }));
  await waitFor(() => expect(lastLocation.pathname).toBe(`/companies/${CO}`));
});

it('clicking a row opens the contact panel', async () => {
  renderAt('/contacts');
  fireEvent.click(await screen.findByText('General Manager · Operations'));
  expect(await screen.findByRole('dialog')).toBeInTheDocument();
});

it('?new=true opens the new-contact form', async () => {
  renderAt('/contacts?new=true');
  expect(await screen.findByRole('dialog')).toBeInTheDocument();
  await waitFor(() => expect(lastLocation.search).toBe(''));
});
