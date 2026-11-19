/**
 * The reply of bulk_operations action=delete lists a result per record; a refused record has
 * deleted=false and the server's reason in `error`. The reply is 200 even when every record
 * was refused, so callers must read the results rather than only the message.
 */
export interface BulkDeleteReply {
  message?: string;
  deleted?: number;
  results?: { id: string; deleted: boolean; error?: string }[];
}

export const summarizeBulkDelete = (
  reply: BulkDeleteReply,
  noun: string,
): { success: string; error: string } => {
  const results = reply.results || [];
  const refused = results.filter((r) => !r.deleted);
  const deleted = reply.deleted ?? results.length - refused.length;
  const success = deleted > 0 ? `${deleted} ${noun}${deleted === 1 ? '' : 's'} deleted` : '';
  const reasons = Array.from(new Set(refused.map((r) => r.error || 'Not deleted.')));
  const error = refused.length
    ? `${refused.length} ${noun}${refused.length === 1 ? '' : 's'} not deleted: ${reasons.join(' ')}`
    : '';
  return { success, error };
};
