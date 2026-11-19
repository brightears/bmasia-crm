/**
 * Log a failed request without the error object itself.
 *
 * An axios error carries the request's headers (the Authorization token) and, for saves,
 * the whole request body. Only the status, method, path and the server's own message are
 * printed. consoleHygiene.test.tsx fails when a raw error object is logged again.
 */
const MAX_MESSAGE = 200;

const serverMessage = (data: unknown): string => {
  if (typeof data === 'string') return data.trim().startsWith('<') ? '' : data;
  if (data && typeof data === 'object') {
    const d = data as Record<string, unknown>;
    for (const key of ['error', 'detail', 'message']) {
      if (typeof d[key] === 'string') return d[key] as string;
    }
  }
  return '';
};

const pathOf = (url: unknown): string => {
  if (typeof url !== 'string' || !url) return '';
  try {
    return new URL(url, 'http://local').pathname;
  } catch {
    return url.split('?')[0];
  }
};

export const describeApiError = (err: unknown): string => {
  const e = err as any;
  if (e && typeof e === 'object' && (e.isAxiosError || e.response || e.config)) {
    const parts = [
      e.response?.status ? String(e.response.status) : (e.code || 'no response'),
      e.config?.method ? String(e.config.method).toUpperCase() : '',
      pathOf(e.config?.url),
      serverMessage(e.response?.data),
    ].filter(Boolean);
    return parts.join(' ').slice(0, MAX_MESSAGE);
  }
  if (err instanceof Error) return err.message.slice(0, MAX_MESSAGE);
  return String(err).slice(0, MAX_MESSAGE);
};

export const logApiError = (context: string, err: unknown): void => {
  // eslint-disable-next-line no-console
  console.error(context, describeApiError(err));
};

/** The server's own explanation of a refused request (for example a refused delete), or the fallback. */
export const apiErrorMessage = (err: unknown, fallback: string): string => {
  const message = serverMessage((err as any)?.response?.data);
  return message || fallback;
};
