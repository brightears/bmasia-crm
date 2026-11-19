// Walks every route in App.tsx for every server role (and for an account without a role)
// and checks that the router, the side menu and the role table agree.
import React from 'react';
import fs from 'fs';
import path from 'path';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '../contexts/ThemeContext';
import App from '../App';
import { buildNavGroups, filterNavForRole } from '../components/navigation';
import { MENU_PATH_MODULE, MODULE_ROLES, SERVER_ROLES, canOpenModule, canSeeMenuPath } from './access';

// No network: requests never answer, so pages stay in their loading state.
jest.mock('axios', () => {
  const inst: any = {
    interceptors: { request: { use: () => 0 }, response: { use: () => 0 } },
    get: () => new Promise(() => {}),
    post: () => new Promise(() => {}),
    patch: () => new Promise(() => {}),
    delete: () => new Promise(() => {}),
    defaults: { headers: { common: {} } },
  };
  return { __esModule: true, default: { create: () => inst, ...inst }, create: () => inst };
});
jest.mock('react-quill-new', () => ({ __esModule: true, default: () => null }));
jest.mock('../services/api', () => {
  const never = () => new Promise(() => {});
  const service = new Proxy({}, { get: () => never });
  return new Proxy({}, { get: (_t, key) => (key === '__esModule' ? true : key === 'default' ? service : never) });
});

let mockUser: any = null;
jest.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: mockUser,
    isAuthenticated: true,
    loading: false,
    logout: () => Promise.resolve(),
    hasPermission: () => false,
    hasRole: () => false,
  }),
}));

interface RouteInfo {
  route: string;
  url: string;
  module: string | undefined;
}

interface RouteTag {
  /** The `path` attribute of the <Route …> opening tag, wherever it sits in the tag. */
  route: string | undefined;
  /** The `element={…}` expression, when there is one. */
  element: string;
  /** The `requiredModule` named inside the element (its <ProtectedRoute>). */
  module: string | undefined;
}

/**
 * Every <Route …> opening tag in a source file, read with a small scanner so attributes may come in any order
 * and tags may span lines: the tag ends at the first ">" outside braces and quotes.
 */
const routeTags = (source: string): RouteTag[] => {
  const tags: RouteTag[] = [];
  const opener = /<Route\b/g;
  let match: RegExpExecArray | null;
  while ((match = opener.exec(source)) !== null) {
    let depth = 0;
    let quote = '';
    let end = match.index + match[0].length;
    let topLevel = '';
    let element = '';
    let elementStart = -1;
    for (; end < source.length; end += 1) {
      const ch = source[end];
      if (quote) {
        if (ch === quote) quote = '';
      } else if (ch === '"') {
        quote = ch;
      } else if (ch === '{') {
        if (depth === 0 && /element=\s*$/.test(topLevel)) elementStart = end + 1;
        depth += 1;
      } else if (ch === '}') {
        depth -= 1;
        if (depth === 0 && elementStart >= 0 && !element) element = source.slice(elementStart, end);
      } else if (ch === '>' && depth === 0) {
        break;
      }
      if (depth === 0) topLevel += ch;
    }
    tags.push({
      route: /\bpath="([^"]+)"/.exec(topLevel)?.[1],
      element,
      module: /requiredModule="([^"]+)"/.exec(element)?.[1],
    });
  }
  return tags;
};

const APP_ROUTES = routeTags(fs.readFileSync(path.join(__dirname, '..', 'App.tsx'), 'utf8'));
const isRedirect = (element: string) => /^\s*<Navigate\b/.test(element);

// Every <Route> in App.tsx, read from the source so routes added later are walked too.
const ROUTES: RouteInfo[] = APP_ROUTES.map((tag): RouteInfo | null => {
  const route = tag.route;
  if (!route || ['/login', '/', '*'].includes(route) || isRedirect(tag.element)) return null;
  const url = route.replace(/\/:[a-zA-Z]+\?/g, '').replace(/:[a-zA-Z]+/g, 'fixture-id');
  return { route, url, module: tag.module };
}).filter((r): r is RouteInfo => r !== null);

// Every <Route> path in App.tsx with whether it has a guard, redirects included, for the allow-list check.
const ALL_ROUTES = APP_ROUTES.filter((tag) => tag.route).map((tag) => ({
  route: tag.route as string,
  redirect: isRedirect(tag.element),
  guarded: Boolean(tag.module),
}));

/**
 * Routes that may have no guard. Anything else added to App.tsx without `requiredModule` would be
 * open to every role, so the test below refuses it.
 */
const UNGUARDED_ALLOWED = [
  '/login', // sign-in
  '/', // redirects by sign-in state
  '/today', // home page; shows its own notice to an account without a role
  '/profile', // every account's own profile
  '/needs-fixing/:key?', // read-only checks; the server decides what it returns
  '/my-queue', // placeholder pages
  '/analytics',
  '/slas',
  '/system-status',
  '/more',
  '*', // the 404 page
];

// The Review menu entry as Layout builds it, with the switch on and off.
const REVIEW_ON = { enabled: true, openCount: 0 };
const REVIEW_OFF = { enabled: false, openCount: 0 };

type Outcome = 'opens' | 'denied' | 'no-role';

const visit = (role: string, url: string): Outcome => {
  mockUser = { id: 'u-1', username: 'fixture', first_name: 'Fixture', last_name: 'User', role, is_active: true };
  render(
    <MemoryRouter initialEntries={[url]}>
      <ThemeProvider>
        <App />
      </ThemeProvider>
    </MemoryRouter>
  );
  const outcome: Outcome = screen.queryByText('Access Denied')
    ? 'denied'
    : screen.queryByTestId('no-role-notice')
      ? 'no-role'
      : 'opens';
  expect(screen.queryByText('This page does not exist')).not.toBeInTheDocument();
  cleanup();
  return outcome;
};

const fetchBefore = global.fetch;
beforeAll(() => {
  (global as any).fetch = () => new Promise(() => {});
  jest.spyOn(console, 'error').mockImplementation(() => {});
  jest.spyOn(console, 'warn').mockImplementation(() => {});
});
afterAll(() => {
  (global as any).fetch = fetchBefore;
  jest.restoreAllMocks();
});

it('reads the routes of App.tsx', () => {
  expect(ROUTES.length).toBeGreaterThan(50);
  expect(ROUTES.filter((r) => r.module).length).toBeGreaterThan(40);
});

it('every route guard names a module of the role table', () => {
  const unknown = ROUTES.filter((r) => r.module && !(r.module in MODULE_ROLES));
  expect(unknown).toEqual([]);
});

it('reads <Route> tags whatever the attribute order, also across lines', () => {
  const tags = routeTags(
    [
      '<Route path="/a" element={<Page />} />',
      '<Route element={<Odd />} path="/sneaky-two" />',
      '<Route\n  element={\n    <ProtectedRoute requiredModule="users">\n      <Users />\n    </ProtectedRoute>\n  }\n  path="/three"\n/>',
      '<Route path="/four" element={<Navigate to="/a" replace />} />',
    ].join('\n'),
  );
  expect(tags.map((t) => [t.route, t.module ?? null, isRedirect(t.element)])).toEqual([
    ['/a', null, false],
    ['/sneaky-two', null, false],
    ['/three', 'users', false],
    ['/four', null, true],
  ]);
  // A path inside the element (not an attribute of the Route) is not taken for the Route's own path.
  expect(routeTags('<Route element={<Link path="/inner" />} />')[0].route).toBeUndefined();
});

it('only the allow-listed routes have no guard', () => {
  const unguarded = ALL_ROUTES.filter((r) => !r.guarded && !r.redirect).map((r) => r.route);
  expect(unguarded.filter((r) => !UNGUARDED_ALLOWED.includes(r))).toEqual([]);
  // The check really reads the routes: the Review page is guarded, Today is not.
  expect(ALL_ROUTES.find((r) => r.route === '/review')?.guarded).toBe(true);
  expect(unguarded).toContain('/today');
});

it('the Review entry is absent for every role while suggestions are switched off', () => {
  for (const role of [...SERVER_ROLES, '']) {
    const paths = filterNavForRole(buildNavGroups(0, REVIEW_OFF), role).flatMap((g) => g.items.map((i) => i.path));
    expect(paths).not.toContain('/review');
  }
  expect(ROUTES.find((r) => r.route === '/review')?.module).toBe('review');
});

it('every menu entry is mapped in the role table and is a route', () => {
  const menuPaths = buildNavGroups(0, REVIEW_ON).flatMap((g) => g.items.map((i) => i.path));
  expect(menuPaths).toContain('/review');
  for (const p of menuPaths) {
    expect(MENU_PATH_MODULE[p]).toBeDefined();
    expect(ROUTES.map((r) => r.route)).toContain(p);
  }
});

const ROLES = [...SERVER_ROLES, ''];

describe.each(ROLES)('role "%s"', (role) => {
  it(
    'opens exactly the routes the table allows, and the menu offers exactly those',
    () => {
      const user = { role, is_active: true };
      const opened = new Map<string, boolean>();
      const wrong: string[] = [];
      for (const r of ROUTES) {
        const outcome = visit(role, r.url);
        const allowed = r.module ? canOpenModule(user, r.module) : true;
        opened.set(r.route, outcome === 'opens');
        if ((outcome === 'opens') !== allowed) wrong.push(`${r.route} (${r.module ?? 'no guard'}): ${outcome}`);
        if (role === '' && outcome === 'denied') wrong.push(`${r.route}: Access Denied instead of the no-role notice`);
      }
      expect(wrong).toEqual([]);

      // The invariant: a menu entry shows if and only if the router opens its page (Review switched on).
      const menu = new Set(
        filterNavForRole(buildNavGroups(0, REVIEW_ON), role).flatMap((g) => g.items.map((i) => i.path))
      );
      const mismatched = buildNavGroups(0, REVIEW_ON)
        .flatMap((g) => g.items.map((i) => i.path))
        .filter((p) => menu.has(p) !== opened.get(p))
        .map((p) => `${p}: menu ${menu.has(p) ? 'shows' : 'hides'}, router ${opened.get(p) ? 'opens' : 'refuses'}`);
      expect(mismatched).toEqual([]);
      for (const p of Array.from(menu)) expect(canSeeMenuPath(user, p)).toBe(true);
    },
    180000
  );
});

it('Admin opens every route in App.tsx', () => {
  const refused = ROUTES.filter((r) => visit('Admin', r.url) !== 'opens').map((r) => r.route);
  expect(refused).toEqual([]);
}, 180000);

it('an account without a role sees Today with a notice and a notice on other pages', () => {
  mockUser = { id: 'u-1', first_name: 'No', last_name: 'Role', role: '', is_active: true };
  render(
    <MemoryRouter initialEntries={['/today']}>
      <ThemeProvider>
        <App />
      </ThemeProvider>
    </MemoryRouter>
  );
  expect(screen.getByTestId('no-role-banner')).toHaveTextContent('Your account has no role yet');
  cleanup();
  expect(visit('', '/companies')).toBe('no-role');
  expect(visit('', '/profile')).toBe('opens');
});

it('spot checks of the table', () => {
  const can = (role: string, m: string) => canOpenModule({ role, is_active: true }, m);
  expect(can('Sales', 'finance-reports')).toBe(false);
  expect(can('Sales', 'users')).toBe(false);
  expect(can('Sales', 'contract-templates')).toBe(true);
  expect(can('Sales', 'seasonal-dates')).toBe(false);
  expect(can('Finance', 'finance-reports')).toBe(true);
  expect(can('Tech', 'tickets')).toBe(true);
  expect(can('Music', 'quotes')).toBe(false);
  expect(canOpenModule({ role: 'Admin', is_active: false }, 'today')).toBe(false);
  expect(canOpenModule({ role: 'Admin', is_active: true }, 'no-such-module')).toBe(false);
  for (const role of SERVER_ROLES) expect(can(role, 'review')).toBe(true);
  expect(can('', 'review')).toBe(false);
  expect(can('Someone new', 'review')).toBe(false);
});
