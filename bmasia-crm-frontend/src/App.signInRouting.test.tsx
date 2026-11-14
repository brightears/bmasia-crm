// Sign-in routing on a fresh page load (reload, or a CRM link opened in a new tab).
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { ThemeProvider } from './contexts/ThemeContext';
import App from './App';

// No network: axios instances and the API client never resolve, so pages stay in their loading state.
jest.mock('axios', () => {
  const inst: any = {
    interceptors: { request: { use: () => 0 }, response: { use: () => 0 } },
    get: () => new Promise(() => {}),
    post: () => new Promise(() => {}),
    defaults: { headers: { common: {} } },
  };
  return { __esModule: true, default: { create: () => inst, ...inst }, create: () => inst };
});
jest.mock('react-quill-new', () => ({ __esModule: true, default: () => null }));
jest.mock('./services/api', () => new Proxy({}, { get: () => () => new Promise(() => {}) }));

const b64 = (o: object) => Buffer.from(JSON.stringify(o)).toString('base64').replace(/=+$/, '');
const fakeJwt = (expSecondsFromNow: number) =>
  `${b64({ alg: 'HS256', typ: 'JWT' })}.${b64({ exp: Math.floor(Date.now() / 1000) + expSecondsFromNow, user_id: 'x' })}.sig`;

const storeSession = () => {
  sessionStorage.setItem('bmasia_access_token', fakeJwt(3600));
  sessionStorage.setItem('bmasia_refresh_token', fakeJwt(7 * 86400));
  sessionStorage.setItem(
    'bmasia_user',
    JSON.stringify({ id: 'x', username: 'u', first_name: 'A', last_name: 'B', role: 'Admin', permissions: [] })
  );
};

let seen: string[] = [];
const Where: React.FC = () => {
  const l = useLocation();
  seen.push(`${l.pathname}${l.search}`);
  return <div data-testid="where">{`${l.pathname}${l.search}`}</div>;
};

const renderAt = (entry: any) =>
  render(
    <MemoryRouter initialEntries={[entry]}>
      <ThemeProvider>
        <AuthProvider>
          <Where />
          <App />
        </AuthProvider>
      </ThemeProvider>
    </MemoryRouter>
  );

beforeEach(() => {
  seen = [];
  sessionStorage.clear();
  localStorage.clear();
});

it('keeps a signed-in user on the page they reloaded', async () => {
  storeSession();
  renderAt('/companies');
  await new Promise((r) => setTimeout(r, 200));
  expect(seen).not.toContain('/login');
  expect(screen.getByTestId('where')).toHaveTextContent('/companies');
  expect(screen.queryByLabelText(/username/i)).not.toBeInTheDocument();
});

it('still sends a signed-out user to sign-in', async () => {
  renderAt('/contracts/abc?tab=documents');
  await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('/login'));
  expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
});

it('sends an already signed-in user away from the sign-in page, back to the page they asked for', async () => {
  storeSession();
  renderAt({ pathname: '/login', state: { from: { pathname: '/contracts/abc', search: '?tab=documents' } } });
  await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('/contracts/abc?tab=documents'));
});

it('sends an already signed-in user from the sign-in page to the default page when nothing was asked for', async () => {
  storeSession();
  renderAt('/login');
  await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('/dashboard'));
});
