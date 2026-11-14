import React from 'react';
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter, MemoryRouter, useLocation, useNavigate } from 'react-router-dom';
import { useListState } from './useListState';
import { useListSearchBox } from './useListSearchBox';

let location: any = null;
let navigate: any = null;
let renders = 0;

/** A list page in miniature: search text in the address, with an optional slow render. */
const List: React.FC<{ slowMs?: number }> = ({ slowMs = 0 }) => {
  const list = useListState({ q: '', page: 0, size: 25 });
  const [search, setSearch] = list.bind('q');
  const [, setPage] = list.bind('page');
  const box = useListSearchBox(search, (text) => {
    setSearch(text);
    setPage(0);
  });
  location = useLocation();
  navigate = useNavigate();
  renders += 1;
  if (slowMs) {
    const end = Date.now() + slowMs;
    while (Date.now() < end) {
      // a page that is slow to draw
    }
  }
  return (
    <>
      <input aria-label="search" value={box.value} onChange={(e) => box.onChange(e.target.value)} />
      <span data-testid="committed">{search}</span>
    </>
  );
};

beforeEach(() => {
  window.history.replaceState({}, '', '/list');
  renders = 0;
});

it('shows each keystroke at once and writes the address about 250 ms after typing stops', () => {
  jest.useFakeTimers();
  try {
    render(
      <MemoryRouter initialEntries={['/list?page=3']}>
        <List />
      </MemoryRouter>
    );
    const input = screen.getByLabelText('search') as HTMLInputElement;
    userEvent.type(input, 'hotel');
    expect(input.value).toBe('hotel');
    expect(location.search).toBe('?page=3');
    act(() => {
      jest.advanceTimersByTime(260);
    });
    expect(location.search).toBe('?q=hotel');
  } finally {
    jest.useRealTimers();
  }
});

it('typing fast into a slow page keeps every character (BrowserRouter, 100 ms render)', async () => {
  render(
    <BrowserRouter>
      <List slowMs={100} />
    </BrowserRouter>
  );
  const input = screen.getByLabelText('search') as HTMLInputElement;
  await userEvent.type(input, 'lumen bay', { delay: 15 });
  expect(input.value).toBe('lumen bay');
  await act(() => new Promise<void>((r) => setTimeout(r, 600)));
  expect(input.value).toBe('lumen bay');
  expect(new URLSearchParams(window.location.search).get('q')).toBe('lumen bay');
});

it('typing with no delay keeps every character (BrowserRouter)', async () => {
  render(
    <BrowserRouter>
      <List />
    </BrowserRouter>
  );
  const input = screen.getByLabelText('search') as HTMLInputElement;
  userEvent.type(input, 'hotel');
  expect(input.value).toBe('hotel');
  await act(() => new Promise<void>((r) => setTimeout(r, 400)));
  expect(input.value).toBe('hotel');
  expect(window.location.search).toBe('?q=hotel');
});

it('a change of the address from outside (a link, Back, clear filters) shows in the box', async () => {
  render(
    <MemoryRouter initialEntries={['/list?q=old']}>
      <List />
    </MemoryRouter>
  );
  const input = screen.getByLabelText('search') as HTMLInputElement;
  expect(input.value).toBe('old');
  act(() => navigate('/list?q=from+a+link'));
  expect(input.value).toBe('from a link');
  act(() => navigate('/list'));
  expect(input.value).toBe('');
});

it('a pending write is dropped when the address changes from outside', async () => {
  render(
    <MemoryRouter initialEntries={['/list']}>
      <List />
    </MemoryRouter>
  );
  const input = screen.getByLabelText('search') as HTMLInputElement;
  userEvent.type(input, 'abc');
  act(() => navigate('/list?q=link'));
  await act(() => new Promise<void>((r) => setTimeout(r, 400)));
  expect(input.value).toBe('link');
  expect(location.search).toBe('?q=link');
});

it('its own write arriving late does not undo newer typing', async () => {
  jest.useFakeTimers();
  try {
    render(
      <MemoryRouter initialEntries={['/list']}>
        <List />
      </MemoryRouter>
    );
    const input = screen.getByLabelText('search') as HTMLInputElement;
    userEvent.type(input, 'lum');
    act(() => {
      jest.advanceTimersByTime(260); // "lum" written to the address
    });
    userEvent.type(input, 'en');
    expect(input.value).toBe('lumen');
    act(() => {
      jest.advanceTimersByTime(260);
    });
    expect(input.value).toBe('lumen');
    expect(location.search).toBe('?q=lumen');
  } finally {
    jest.useRealTimers();
  }
});

it('one address update per pause in typing, not one per keystroke', () => {
  jest.useFakeTimers();
  try {
    render(
      <MemoryRouter initialEntries={['/list']}>
        <List />
      </MemoryRouter>
    );
    const input = screen.getByLabelText('search') as HTMLInputElement;
    const before = renders;
    userEvent.type(input, 'resort');
    const typingRenders = renders - before;
    act(() => {
      jest.advanceTimersByTime(260);
    });
    expect(typingRenders).toBe(6); // one per keystroke, for the box only
    expect(location.search).toBe('?q=resort');
  } finally {
    jest.useRealTimers();
  }
});
