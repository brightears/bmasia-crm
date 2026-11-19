import React from 'react';
import fs from 'fs';
import path from 'path';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ContactForm from './components/ContactForm';
import ApiService from './services/api';

jest.mock('axios', () => {
  const instance: any = {
    interceptors: { request: { use: jest.fn() }, response: { use: jest.fn() } },
    defaults: { headers: { common: {} } },
    get: jest.fn(), post: jest.fn(),
  };
  return { __esModule: true, default: { ...instance, create: () => instance }, create: () => instance };
});
jest.mock('./services/api', () => ({
  __esModule: true,
  default: { updateContact: jest.fn(), createContact: jest.fn() },
}));

const api = ApiService as unknown as { updateContact: jest.Mock };

afterEach(() => jest.restoreAllMocks());

test('the production entry point defines no window.debugAPI and logs nothing at start-up', () => {
  const source = fs.readFileSync(path.join(__dirname, 'index.tsx'), 'utf8');
  expect(source).not.toMatch(/debugAPI/);
  expect(source).not.toMatch(/console\./);
});

test('loading the auth service does not log the environment', () => {
  const log = jest.spyOn(console, 'log').mockImplementation(() => {});
  jest.isolateModules(() => {
    require('./services/authService');
  });
  const printed = log.mock.calls.flat().map(String).join(' ');
  expect(printed).not.toMatch(/REACT_APP_|NODE_ENV|API_BASE_URL|baseURL|transformResponse/);
});

test('saving a contact does not write the contact to the console', async () => {
  const log = jest.spyOn(console, 'log').mockImplementation(() => {});
  const error = jest.spyOn(console, 'error').mockImplementation(() => {});
  api.updateContact.mockResolvedValue({});
  const onSave = jest.fn();
  const contact: any = {
    id: 'c-1', name: 'Mali Example', email: 'mali@example.com', phone: '+66 2 000 0000',
    company: 'co-1', title: 'Manager', is_active: true, contact_type: 'Primary',
  };
  render(
    <ContactForm open onClose={jest.fn()} onSave={onSave} contact={contact}
      companies={[{ id: 'co-1', name: 'Fixture Resort' } as any]} />,
  );

  fireEvent.click(screen.getByRole('button', { name: 'Update Contact' }));
  await waitFor(() => expect(onSave).toHaveBeenCalled());

  const printed = [...log.mock.calls, ...error.mock.calls].flat().map(String).join(' ');
  expect(printed).not.toContain('mali@example.com');
  expect(printed).not.toContain('Mali');
  expect(log).not.toHaveBeenCalled();
});
