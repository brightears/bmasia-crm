import reviewApi, { ReviewApiError } from './reviewApi';
import { authApi } from './authService';

// The real client code, with only the shared axios instance replaced: these tests read the HTTP calls it makes.
jest.mock('./authService', () => ({
  __esModule: true,
  default: {},
  authApi: { get: jest.fn(), post: jest.fn() },
}));

const http = authApi as unknown as { get: jest.Mock; post: jest.Mock };

beforeEach(() => {
  http.get.mockReset();
  http.post.mockReset();
  http.post.mockResolvedValue({ data: {} });
  http.get.mockResolvedValue({ data: { count: 0, next: null, previous: null, results: [] } });
});

describe('every decision carries the seen_version in the request body', () => {
  it('accept', async () => {
    await reviewApi.accept('p-1', 'v-a');
    expect(http.post).toHaveBeenCalledWith('/change-proposals/p-1/accept/', { seen_version: 'v-a' });
  });

  it('accept with edits', async () => {
    await reviewApi.acceptWithEdits('p-1', 'v-e', { phone: '+66 2 000 1111' }, ['city']);
    expect(http.post).toHaveBeenCalledWith('/change-proposals/p-1/accept-with-edits/', {
      seen_version: 'v-e',
      edits: { phone: '+66 2 000 1111' },
      drop_fields: ['city'],
    });
  });

  it('reject', async () => {
    await reviewApi.reject('p-1', 'v-r', 'Wrong record');
    expect(http.post).toHaveBeenCalledWith('/change-proposals/p-1/reject/', {
      seen_version: 'v-r',
      reason: 'Wrong record',
    });
  });

  it('reopen', async () => {
    await reviewApi.reopen('p-1', 'v-o', 'Looked again');
    expect(http.post).toHaveBeenCalledWith('/change-proposals/p-1/reopen/', {
      seen_version: 'v-o',
      note: 'Looked again',
    });
  });

  it('bulk reject, per item', async () => {
    await reviewApi.bulkReject(
      [
        { id: 'p-1', seen_version: 'v1' },
        { id: 'p-2', seen_version: 'v2' },
      ],
      'Not worth recording',
    );
    expect(http.post).toHaveBeenCalledWith('/change-proposals/bulk-reject/', {
      items: [
        { id: 'p-1', seen_version: 'v1' },
        { id: 'p-2', seen_version: 'v2' },
      ],
      reason: 'Not worth recording',
    });
  });
});

describe('the inactive acknowledgement', () => {
  it('is sent only when asked for', async () => {
    await reviewApi.accept('p-1', 'v-a', { acknowledgeInactive: true });
    expect(http.post).toHaveBeenLastCalledWith('/change-proposals/p-1/accept/', {
      seen_version: 'v-a',
      acknowledge_inactive: true,
    });
    await reviewApi.acceptWithEdits('p-1', 'v-e', { city: 'X' }, [], { acknowledgeInactive: true });
    expect(http.post).toHaveBeenLastCalledWith('/change-proposals/p-1/accept-with-edits/', {
      seen_version: 'v-e',
      edits: { city: 'X' },
      acknowledge_inactive: true,
    });
    await reviewApi.accept('p-1', 'v-b');
    expect(http.post).toHaveBeenLastCalledWith('/change-proposals/p-1/accept/', { seen_version: 'v-b' });
  });
});

describe('reads and errors', () => {
  it('reads open suggestions a page at a time, in the order asked for', async () => {
    await reviewApi.listOpen(2, 'expiring');
    const params: URLSearchParams = http.get.mock.calls[0][1].params;
    expect(http.get.mock.calls[0][0]).toBe('/change-proposals/');
    expect(params.getAll('status')).toEqual(['proposed']);
    expect(params.get('page')).toBe('2');
    expect(params.get('page_size')).toBe('200');
    expect(params.get('ordering')).toBe('expires_at');
  });

  it('keeps the code, detail and snapshot of a refusal, and says when no answer came', async () => {
    http.post.mockRejectedValueOnce({
      response: {
        status: 409,
        data: { code: 'stale_view', detail: 'Changed.', proposal: { id: 'p-1', seen_version: 'v2' } },
      },
    });
    const refused = await reviewApi.accept('p-1', 'v1').catch((e) => e);
    expect(refused).toBeInstanceOf(ReviewApiError);
    expect([refused.status, refused.code, refused.detail, refused.snapshot.seen_version]).toEqual([
      409,
      'stale_view',
      'Changed.',
      'v2',
    ]);
    http.post.mockRejectedValueOnce(new Error('timeout'));
    const lost = await reviewApi.accept('p-1', 'v1').catch((e) => e);
    expect(lost.noAnswer).toBe(true);
    expect(http.post).toHaveBeenCalledTimes(2);
  });

  it('shows the shared handler’s message and reference for an unexpected server error', async () => {
    http.post.mockRejectedValueOnce({
      response: {
        status: 500,
        data: { error: 'Something went wrong on the server. Reference: abc12345', request_id: 'abc12345' },
      },
    });
    const failed = await reviewApi.accept('p-1', 'v1').catch((e) => e);
    expect([failed.status, failed.code, failed.detail]).toEqual([
      500,
      undefined,
      'Something went wrong on the server. Reference: abc12345',
    ]);
  });

  it('escapes the contact id in the path', async () => {
    http.get.mockResolvedValueOnce({ data: {} });
    await reviewApi.getContact('../users/1');
    expect(http.get).toHaveBeenCalledWith('/contacts/..%2Fusers%2F1/');
  });
});
