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
      if (G.__refresh === '500') return Promise.reject(fail(500, '<html>Server Error</html>'));
      if (G.__refresh === '403-token') return Promise.reject(fail(403, { detail: 'Token is invalid or expired', code: 'token_not_valid' }));
      if (G.__refresh === 'noaccess') return Promise.resolve(respond(200, '<html>proxy page</html>'));
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
let onLoginPage = false;
beforeEach(() => {
  G.__calls = [];
  G.__newAccess = fakeJwt(3600, 'refreshed');
  localStorage.clear();
  sessionStorage.clear();
  redirects = 0;
  onLoginPage = false;
  AuthService.redirectAfterExpiredSession = () => {
    if (onLoginPage) return false;
    redirects += 1;
    return true;
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

  it.each(['network', '500', 'noaccess'])(
    'refresh fails without a rejection (%s): one call, saved session kept, still signed in',
    async (mode) => {
      G.__refresh = mode;
      storeSession(-60, 6 * 86400);
      const savedRefresh = localStorage.getItem('bmasia_refresh_token');
      render(<AuthProvider><Probe /></AuthProvider>);
      await wait(300);
      expect(refreshCalls()).toBe(1);
      expect(state).toEqual({ loading: false, isAuthenticated: true });
      expect(localStorage.getItem('bmasia_refresh_token')).toBe(savedRefresh);
      expect(localStorage.getItem('bmasia_access_token')).not.toBe('undefined');
    }
  );

  it('403 token_not_valid counts as a rejection: session cleared, signed out', async () => {
    G.__refresh = '403-token';
    storeSession(-60, 6 * 86400);
    render(<AuthProvider><Probe /></AuthProvider>);
    await wait(300);
    expect(state).toEqual({ loading: false, isAuthenticated: false });
    expect(localStorage.getItem('bmasia_refresh_token')).toBeNull();
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

describe('during use, when the refresh fails without a rejection', () => {
  const api = () => (AuthService as any).api;

  it.each(['network', '500', 'noaccess'])('%s: the call fails, the saved session stays, no reload', async (mode) => {
    G.__refresh = mode;
    storeSession(3600, 6 * 86400);
    const savedRefresh = localStorage.getItem('bmasia_refresh_token');
    await expect(api().get('/companies/')).rejects.toBeTruthy();
    expect(refreshCalls()).toBe(1);
    expect(localStorage.getItem('bmasia_refresh_token')).toBe(savedRefresh);
    expect(redirects).toBe(0);
  });
});

describe('the one-reload guard', () => {
  const api = () => (AuthService as any).api;

  it('is not used up on the sign-in page, and is reset by signing in', async () => {
    G.__refresh = 'revoked';
    onLoginPage = true;
    storeSession(3600, 6 * 86400);
    await expect(api().get('/companies/')).rejects.toBeTruthy();
    expect(redirects).toBe(0); // no reload on /login, guard not used up

    onLoginPage = false;
    storeSession(3600, 6 * 86400);
    await expect(api().get('/companies/')).rejects.toBeTruthy();
    expect(redirects).toBe(1);

    // A sign-in resets the guard, so a later expiry reloads again.
    const realPost = (AuthService as any).api.post;
    (AuthService as any).api.post = jest.fn().mockResolvedValue({
      data: { access: fakeJwt(3600, 'new'), refresh: fakeJwt(86400, 'new'), user },
    });
    try {
      await AuthService.login({ username: 'u', password: 'p', remember_me: true } as any);
    } finally {
      (AuthService as any).api.post = realPost;
    }
    storeSession(3600, 6 * 86400);
    await expect(api().get('/companies/')).rejects.toBeTruthy();
    expect(redirects).toBe(2);
  });
});

describe('the scheduled refresh (about 5 minutes before the access token expires)', () => {
  it('keeps the session when the refresh fails without a rejection', async () => {
    G.__refresh = 'network';
    storeSession(301, 6 * 86400); // timer fires after about 1 s
    AuthService.scheduleTokenRefresh();
    await wait(1600);
    expect(refreshCalls()).toBe(1);
    expect(localStorage.getItem('bmasia_refresh_token')).not.toBeNull();
    expect(redirects).toBe(0);
  });

  it('clears the session and reloads once when the server rejects the refresh', async () => {
    G.__refresh = 'revoked';
    storeSession(301, 6 * 86400);
    AuthService.scheduleTokenRefresh();
    await wait(1600);
    expect(localStorage.getItem('bmasia_refresh_token')).toBeNull();
    expect(redirects).toBe(1);
  });
});
