// Refreshing a saved session: real axios and the real AuthService interceptors, with a fake
// adapter that answers /auth/refresh/ the way the server would.
import React from 'react';
import { act, render } from '@testing-library/react';

jest.mock('axios', () => {
  const util = require('util');
  Object.assign(globalThis, { TextEncoder: util.TextEncoder, TextDecoder: util.TextDecoder });
  const actual = jest.requireActual('../../node_modules/axios/dist/node/axios.cjs');
  const adapter = (config: any) => {
    const G: any = globalThis;
    G.__calls.push(`${config.method} ${config.url}`);
    const respond = (status: number, data: any) => ({ data, status, statusText: String(status), headers: {}, config, request: {} });
    const fail = (status: number, data: any) =>
      new actual.AxiosError(String(status), 'ERR_BAD_REQUEST', config, {}, respond(status, data));
    if (String(config.url).includes('/auth/refresh/')) {
      if (G.__refresh === 'ok') return Promise.resolve(respond(200, { access: G.__newAccess }));
      if (G.__refresh === 'network') {
        return Promise.reject(new actual.AxiosError('Network Error', 'ERR_NETWORK', config, {}));
      }
      // 'expired' and 'revoked' both come back as 401 from the server
      return new Promise((_res, rej) => setTimeout(() => rej(fail(401, { detail: 'Token is invalid or expired' })), 5));
    }
    if (String(config.url).includes('/companies/')) {
      // A normal API call: 401 while the access token is stale, 200 once it was refreshed.
      const auth = config.headers?.Authorization || config.headers?.get?.('Authorization');
      if (auth === `Bearer ${G.__newAccess}`) return Promise.resolve(respond(200, { results: [] }));
      return Promise.reject(fail(401, { detail: 'Given token not valid' }));
    }
    return new Promise(() => {});
  };
  const realCreate = actual.create.bind(actual);
  const create = (cfg: any = {}) => realCreate({ ...cfg, adapter });
  const def = realCreate({ adapter });
  return { __esModule: true, AxiosError: actual.AxiosError, default: Object.assign(def, { create, AxiosError: actual.AxiosError }), create };
});

// eslint-disable-next-line import/first
import AuthService from './authService';
// eslint-disable-next-line import/first
import { AuthProvider, useAuth } from '../contexts/AuthContext';

const G: any = globalThis;
const b64 = (o: object) => Buffer.from(JSON.stringify(o)).toString('base64').replace(/=+$/, '');
const fakeJwt = (expSecondsFromNow: number, jti = 'saved') =>
  `${b64({ alg: 'HS256', typ: 'JWT' })}.${b64({ exp: Math.floor(Date.now() / 1000) + expSecondsFromNow, user_id: 'x', jti })}.sig`;
const user = { id: 'x', username: 'u', first_name: 'A', last_name: 'B', role: 'Admin', permissions: [] };

const storeSession = (accessExp: number, refreshExp: number) => {
  localStorage.setItem('bmasia_remember_me', 'true');
  localStorage.setItem('bmasia_access_token', fakeJwt(accessExp));
  localStorage.setItem('bmasia_refresh_token', fakeJwt(refreshExp));
  localStorage.setItem('bmasia_user', JSON.stringify(user));
};

let state: { loading: boolean; isAuthenticated: boolean } = { loading: true, isAuthenticated: false };
const Probe: React.FC = () => {
  const { loading, isAuthenticated } = useAuth();
  state = { loading, isAuthenticated };
  return null;
};

const wait = (ms: number) => act(() => new Promise<void>((r) => setTimeout(r, ms)));
const refreshCalls = () => G.__calls.filter((c: string) => c.includes('/auth/refresh/')).length;

let redirects = 0;
beforeEach(() => {
  G.__calls = [];
  G.__newAccess = fakeJwt(3600, 'refreshed');
  localStorage.clear();
  sessionStorage.clear();
  redirects = 0;
  AuthService.redirectAfterExpiredSession = () => {
    redirects += 1;
  };
  (AuthService as any).sessionExpiredHandled = false;
  state = { loading: true, isAuthenticated: false };
});

describe('on app start, with an expired access token', () => {
  it('expired refresh token: one refresh call, saved session cleared, signed out', async () => {
    G.__refresh = 'expired';
    storeSession(-60, -10);
    render(<AuthProvider><Probe /></AuthProvider>);
    await wait(300);
    expect(refreshCalls()).toBe(1);
    expect(state).toEqual({ loading: false, isAuthenticated: false });
    expect(localStorage.getItem('bmasia_refresh_token')).toBeNull();
    expect(localStorage.getItem('bmasia_access_token')).toBeNull();
  });

  it('revoked refresh token (not yet expired, server says 401): same, no loop', async () => {
    G.__refresh = 'revoked';
    storeSession(-60, 6 * 86400);
    render(<AuthProvider><Probe /></AuthProvider>);
    await wait(300);
    expect(refreshCalls()).toBe(1);
    expect(state).toEqual({ loading: false, isAuthenticated: false });
    expect(localStorage.getItem('bmasia_refresh_token')).toBeNull();
  });

  it('network failure on refresh: one call, signed out, no loop', async () => {
    G.__refresh = 'network';
    storeSession(-60, 6 * 86400);
    render(<AuthProvider><Probe /></AuthProvider>);
    await wait(300);
    expect(refreshCalls()).toBe(1);
    expect(state).toEqual({ loading: false, isAuthenticated: false });
  });

  it('valid refresh token: one refresh call, signed in with the new access token', async () => {
    G.__refresh = 'ok';
    storeSession(-60, 6 * 86400);
    render(<AuthProvider><Probe /></AuthProvider>);
    await wait(300);
    expect(refreshCalls()).toBe(1);
    expect(state).toEqual({ loading: false, isAuthenticated: true });
    expect(localStorage.getItem('bmasia_access_token')).toBe(G.__newAccess);
  });
});

describe('during use, when an API call gets 401', () => {
  const api = () => (AuthService as any).api;

  it('refreshes once and retries the call when the refresh works', async () => {
    G.__refresh = 'ok';
    storeSession(3600, 6 * 86400);
    const res = await api().get('/companies/');
    expect(res.status).toBe(200);
    expect(refreshCalls()).toBe(1);
    expect(redirects).toBe(0);
  });

  it('when the refresh is refused: no loop, session cleared, one redirect for several failing calls', async () => {
    G.__refresh = 'revoked';
    storeSession(3600, 6 * 86400);
    const results = await Promise.allSettled([api().get('/companies/'), api().get('/companies/')]);
    expect(results.every((r) => r.status === 'rejected')).toBe(true);
    expect(refreshCalls()).toBe(2); // one per failing call, never a refresh of a refresh
    expect(localStorage.getItem('bmasia_refresh_token')).toBeNull();
    expect(redirects).toBe(1);
  });
});
