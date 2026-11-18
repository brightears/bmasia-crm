import fs from 'fs';
import path from 'path';
import { describeApiError, logApiError } from './logApiError';

const axiosError = (over: any = {}) => ({
  isAxiosError: true,
  message: 'Request failed with status code 409',
  config: {
    method: 'post',
    url: 'https://crm.example.com/api/v1/companies/c-1/?page=2',
    headers: { Authorization: 'Bearer secret-access-token' },
    data: JSON.stringify({ name: 'Private Name', email: 'private@example.com' }),
  },
  response: { status: 409, data: { error: 'Keep Me Resort cannot be deleted.' } },
  ...over,
});

afterEach(() => jest.restoreAllMocks());

test('prints status, method, path and the server message only', () => {
  expect(describeApiError(axiosError())).toBe('409 POST /api/v1/companies/c-1/ Keep Me Resort cannot be deleted.');
});

test('never prints the token or the request body, and hands the console only strings', () => {
  const log = jest.spyOn(console, 'error').mockImplementation(() => {});
  logApiError('Delete company error:', axiosError());
  // Checked structurally: an object argument would show its headers in the browser console.
  log.mock.calls.flat().forEach((arg) => expect(typeof arg).toBe('string'));
  const printed = log.mock.calls.flat().join(' ');
  expect(printed).not.toContain('secret-access-token');
  expect(printed).not.toContain('private@example.com');
  expect(printed).toContain('Delete company error:');
});

test('a network error without a response and a plain error are described too', () => {
  expect(describeApiError(axiosError({ response: undefined, code: 'ERR_NETWORK' }))).toBe(
    'ERR_NETWORK POST /api/v1/companies/c-1/');
  expect(describeApiError(new Error('boom'))).toBe('boom');
  expect(describeApiError(axiosError({ response: { status: 500, data: '<html>Server Error</html>' } })))
    .toBe('500 POST /api/v1/companies/c-1/');
});

// Files a named open change still edits or deletes, with the number of raw logs they hold now.
// Not a permanent list: the test fails when a file gains a raw log, and when it loses one
// (then lower the count, or drop the entry once it reaches zero).
const NOT_YET: Record<string, { change: string; rawLogs: number }> = {
  'components/OpportunityForm.tsx': { change: 'PR 60 (company timeline) rewrites it', rawLogs: 3 },
  'components/ContractDetail.tsx': { change: 'PR 60 (company timeline) rewrites it', rawLogs: 7 },
  'components/ActivityTimeline.tsx': { change: 'PR 60 (company timeline) deletes it', rawLogs: 2 },
  'pages/ActivityDemo.tsx': { change: 'PR 60 (company timeline) deletes it', rawLogs: 1 },
};

const sourceFiles = (dir: string): string[] =>
  fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return sourceFiles(full);
    return /\.(ts|tsx)$/.test(entry.name) && !/\.test\./.test(entry.name) ? [full] : [];
  });

const rawLogs = (text: string): string[] => {
  const caught = new Set(Array.from(text.matchAll(/catch\s*\(\s*\(?\s*([A-Za-z_$][\w$]*)/g)).map((m) => m[1]));
  if (!caught.size) return [];
  return Array.from(text.matchAll(/console\.(?:error|warn|log|info|debug)\(([^;]*?)\);/g))
    .filter((call) => call[1].split(',').map((a) => a.trim()).some((a) => caught.has(a)))
    .map((call) => call[0].slice(0, 60));
};

test('no source file logs a caught error object to the console', () => {
  const src = path.join(__dirname, '..');
  const offenders: string[] = [];
  const exemptCounts: Record<string, number> = {};
  sourceFiles(src).forEach((file) => {
    const rel = path.relative(src, file).split(path.sep).join('/');
    if (rel === 'utils/logApiError.ts') return;
    const found = rawLogs(fs.readFileSync(file, 'utf8'));
    if (rel in NOT_YET) {
      exemptCounts[rel] = found.length;
    } else {
      found.forEach((call) => offenders.push(`${rel}: ${call}`));
    }
  });
  expect(offenders).toEqual([]);
  // The exemptions shrink: a file that gained or lost a raw log fails here.
  const expected = Object.fromEntries(Object.entries(NOT_YET).map(([rel, entry]) => [rel, entry.rawLogs]));
  expect(exemptCounts).toEqual(expected);
});
