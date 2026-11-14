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
