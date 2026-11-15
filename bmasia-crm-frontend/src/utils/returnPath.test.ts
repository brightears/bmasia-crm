import { safeReturnPath } from './returnPath';

describe('safeReturnPath', () => {
  it('keeps same-app paths with their query string', () => {
    expect(safeReturnPath({ pathname: '/contracts/abc', search: '?tab=documents' }, '/home')).toBe('/contracts/abc?tab=documents');
    expect(safeReturnPath({ pathname: '/' }, '/home')).toBe('/');
    expect(safeReturnPath({ pathname: '/contracts/%2F%2Fevil.example' }, '/home')).toBe('/contracts/%2F%2Fevil.example');
  });

  it('rejects anything that could leave the app', () => {
    for (const pathname of ['//evil.example', '/\\evil.example', 'https://evil.example', 'javascript:alert(1)', 'evil', '', ' /x', '/\t/evil.example', '/\n/evil.example', '/\r/evil.example', '/\t\\evil.example', '/x\u0000y']) {
      expect(safeReturnPath({ pathname }, '/home')).toBe('/home');
    }
  });

  it('falls back when nothing usable was remembered', () => {
    expect(safeReturnPath(undefined, '/home')).toBe('/home');
    expect(safeReturnPath(null, '/home')).toBe('/home');
    expect(safeReturnPath({ pathname: 42 }, '/home')).toBe('/home');
    expect(safeReturnPath({ pathname: '/x', search: 'no-question-mark' }, '/home')).toBe('/x');
    expect(safeReturnPath({ pathname: '/x', search: '?a=1\n' }, '/home')).toBe('/x');
  });
});
