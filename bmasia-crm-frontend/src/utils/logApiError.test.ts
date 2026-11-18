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

test('never prints the token or the request body', () => {
  const log = jest.spyOn(console, 'error').mockImplementation(() => {});
  logApiError('Delete company error:', axiosError());
  const printed = log.mock.calls.flat().map(String).join(' ');
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

// Files the company-timeline change (PR 60) edits or deletes; done after it merges.
const NOT_YET = new Set([
  'components/OpportunityForm.tsx',
  'components/ContractDetail.tsx',
  'components/ActivityTimeline.tsx',
  'pages/ActivityDemo.tsx',
  // Its only raw log is in the attachment upload that fix/invoice-paid-and-attachments removes.
  'components/QuoteForm.tsx',
]);

const sourceFiles = (dir: string): string[] =>
  fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return sourceFiles(full);
    return /\.(ts|tsx)$/.test(entry.name) && !/\.test\./.test(entry.name) ? [full] : [];
  });

test('no source file logs a caught error object to the console', () => {
  const src = path.join(__dirname, '..');
  const offenders: string[] = [];
  sourceFiles(src).forEach((file) => {
    const rel = path.relative(src, file).split(path.sep).join('/');
    if (NOT_YET.has(rel) || rel === 'utils/logApiError.ts') return;
    const text = fs.readFileSync(file, 'utf8');
    const caught = new Set(
      Array.from(text.matchAll(/catch\s*\(\s*\(?\s*([A-Za-z_$][\w$]*)/g)).map((m) => m[1]),
    );
    if (!caught.size) return;
    Array.from(text.matchAll(/console\.(?:error|warn|log|info|debug)\(([^;]*?)\);/g)).forEach((call) => {
      const args = call[1].split(',').map((a) => a.trim());
      if (args.some((a) => caught.has(a))) {
        offenders.push(`${rel}: console.${call[0].slice(8, 40)}`);
      }
    });
  });
  expect(offenders).toEqual([]);
});
