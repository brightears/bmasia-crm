import React from 'react';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { useListReturnPath, withListView } from './listReturn';

let path = '';
const Probe: React.FC = () => {
  path = useListReturnPath('/quotes');
  return null;
};
const renderWith = (state: unknown) =>
  render(
    <MemoryRouter initialEntries={[{ pathname: '/quotes/q-1', state }]}>
      <Probe />
    </MemoryRouter>
  );

it('returns to the list view the user came from', () => {
  renderWith(withListView(new URLSearchParams('status=Sent&page=2')).state);
  expect(path).toBe('/quotes?status=Sent&page=2');
});

it('falls back to the plain list when opened another way', () => {
  renderWith(null);
  expect(path).toBe('/quotes');
  renderWith({ listSearch: 42 });
  expect(path).toBe('/quotes');
});
