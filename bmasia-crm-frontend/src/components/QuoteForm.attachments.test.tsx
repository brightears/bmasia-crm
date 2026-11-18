import React from 'react';
import { render, screen } from '@testing-library/react';
import QuoteForm from './QuoteForm';

jest.mock('react-quill-new', () => ({ __esModule: true, default: () => null }));
jest.mock('../services/api', () => ({
  __esModule: true,
  default: new Proxy({}, { get: () => () => new Promise(() => {}) }),
}));

test('the quote form says attachments are not available instead of offering an upload', () => {
  render(
    <QuoteForm open onClose={jest.fn()} onSave={jest.fn()} mode="create" companies={[]} contacts={[]} opportunities={[]} />,
  );
  expect(screen.getByTestId('quote-attachments-unavailable')).toHaveTextContent(
    'File attachments for quotes are not available yet',
  );
  expect(screen.queryByText('Upload Files')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /upload/i })).not.toBeInTheDocument();
});
