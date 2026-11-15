import React from 'react';
import { act, render } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { useListState } from './useListState';

let api: any = null;
let location: any = null;
const Probe: React.FC = () => {
  api = useListState({ q: '', status: '', sort: '-created_at', page: 0, size: 25 });
  location = useLocation();
  return null;
};

const renderAt = (url: string) =>
  render(
    <MemoryRouter initialEntries={[url]}>
      <Probe />
    </MemoryRouter>
  );

it('reads values from the address, with defaults and a 1-based page', () => {
  renderAt('/list?q=lumen&page=3&size=50');
  expect(api.values).toEqual({ q: 'lumen', status: '', sort: '-created_at', page: 2, size: 50 });
});

it('falls back to defaults for missing or invalid values', () => {
  renderAt('/list?page=abc');
  expect(api.values.page).toBe(0);
});

it('combines several updates in one event and drops defaults', () => {
  renderAt('/list?page=4&sort=name');
  act(() => {
    const [, setStatus] = api.bind('status');
    const [, setPage] = api.bind('page');
    const [, setSort] = api.bind('sort');
    setStatus('Sent');
    setPage(0);
    setSort('-created_at');
  });
  expect(location.search).toBe('?status=Sent');
  expect(api.values.status).toBe('Sent');
  expect(api.values.page).toBe(0);
});

it('writes page as 1-based', () => {
  renderAt('/list');
  act(() => api.set('page', 1));
  expect(location.search).toBe('?page=2');
});

it('a setter kept from an earlier render does not undo later changes', () => {
  renderAt('/list');
  const [, staleSetStatus] = api.bind('status'); // kept, as in a useCallback with no dependencies
  act(() => api.set('q', 'lumen'));
  expect(location.search).toBe('?q=lumen');
  act(() => staleSetStatus('Sent'));
  expect(location.search).toBe('?q=lumen&status=Sent');
});

describe('values from the address are checked', () => {
  const Checked: React.FC = () => {
    api = useListState(
      { q: '', status: '', sort: '-created_at', page: 0, size: 25 },
      { status: ['', 'Draft', 'Sent'], sort: ['-created_at', 'name'] }
    );
    location = useLocation();
    return null;
  };
  const renderChecked = (url: string) =>
    render(
      <MemoryRouter initialEntries={[url]}>
        <Checked />
      </MemoryRouter>
    );

  it.each(['-5', '0', '7', '99999', '25abc', 'abc'])('rows per page %s falls back to the default', (size) => {
    renderChecked(`/list?size=${size}`);
    expect(api.values.size).toBe(25);
  });

  it('accepts the page-size choices', () => {
    renderChecked('/list?size=100');
    expect(api.values.size).toBe(100);
  });

  it('an unknown filter or sort falls back to "all" / the default', () => {
    renderChecked('/list?status=Bogus&sort=password');
    expect(api.values.status).toBe('');
    expect(api.values.sort).toBe('-created_at');
  });

  it('known values are kept', () => {
    renderChecked('/list?status=Sent&sort=name&page=3');
    expect(api.values).toMatchObject({ status: 'Sent', sort: 'name', page: 2 });
  });

  it('a negative or fractional page falls back to the first page', () => {
    renderChecked('/list?page=-3');
    expect(api.values.page).toBe(0);
    renderChecked('/list?page=2.7');
    expect(api.values.page).toBe(0);
  });
});

describe('record-id filters', () => {
  const { idFromList, isRecordId } = jest.requireActual('./useListState');
  it('accepts UUIDs and whole numbers only', () => {
    expect(isRecordId('9e522106-93f0-49c9-82f5-b638c7eb3b29')).toBe(true);
    expect(isRecordId('42')).toBe(true);
    expect(isRecordId("1' or 1=1")).toBe(false);
  });
  it('once the list has loaded, the id must be in it', () => {
    const check = idFromList([{ id: 'a1b2c3d4-0000-0000-0000-000000000001' }], 'all');
    expect(check('all')).toBe(true);
    expect(check('a1b2c3d4-0000-0000-0000-000000000001')).toBe(true);
    expect(check('a1b2c3d4-0000-0000-0000-000000000002')).toBe(false);
    expect(idFromList([])('a1b2c3d4-0000-0000-0000-000000000002')).toBe(true); // not loaded yet: shape only
  });
});
