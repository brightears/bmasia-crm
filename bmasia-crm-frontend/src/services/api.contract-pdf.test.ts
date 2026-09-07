jest.mock('./authService', () => ({
  authApi: {
    get: jest.fn(),
    post: jest.fn(),
    patch: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
  },
}));

import {
  ContractPdfDownloadError,
  parseContractPdfDownloadError,
} from './api';
import ApiService from './api';
import { authApi } from './authService';


test('parses structured Hilton PDF blockers returned as an Axios Blob', async () => {
  const payload = {
    error: 'Hilton Participation Agreement PDF blocked.',
    blockers: [
      {
        code: 'missing_attachment_b',
        detail: 'Attach the approved Hilton Attachment B.',
      },
      {
        code: 'missing_hotel_contact',
        detail: 'Provide one verified hotel contact.',
      },
    ],
  };
  const error = {
    response: {
      status: 409,
      data: new Blob([JSON.stringify(payload)], { type: 'application/json' }),
    },
  };

  const parsed = await parseContractPdfDownloadError(error);

  expect(parsed).toBeInstanceOf(ContractPdfDownloadError);
  expect(parsed.message).toContain('[missing_attachment_b] Attach the approved Hilton Attachment B.');
  expect(parsed.message).toContain('[missing_hotel_contact] Provide one verified hotel contact.');
  expect((parsed as ContractPdfDownloadError).status).toBe(409);
});


test('contract email send preserves actionable Hilton blockers from a JSON 409', async () => {
  const blocker = {
    code: 'missing_attachment_b',
    detail: 'Attach the approved Hilton Attachment B.',
  };
  (authApi.post as jest.Mock).mockRejectedValueOnce({
    response: {
      status: 409,
      data: {
        error: 'Hilton Participation Agreement PDF blocked.',
        blockers: [blocker],
      },
    },
  });

  await expect(ApiService.sendContractEmail('contract-1', {
    recipients: ['joan.deng@hilton.com'],
    cc: [],
    subject: 'Hilton Participation Agreement',
    body: 'Please review the agreement.',
  })).rejects.toMatchObject({
    name: 'ContractPdfDownloadError',
    status: 409,
    blockers: [blocker],
    message: expect.stringContaining('[missing_attachment_b] Attach the approved Hilton Attachment B.'),
  });
});
