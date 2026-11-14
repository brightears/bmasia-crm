/**
 * One colour language for statuses across the app (display only).
 * green = good / done, blue = in progress / waiting on the customer,
 * amber = needs attention soon, red = problem or lost, grey = not started / inactive.
 */
export type StatusTone = 'success' | 'info' | 'warning' | 'error' | 'default' | 'primary';

const TONES: Record<string, StatusTone> = {
  // good / done
  active: 'success',
  paid: 'success',
  won: 'success',
  signed: 'success',
  accepted: 'success',
  online: 'success',
  resolved: 'success',
  done: 'success',
  completed: 'success',
  // in progress / waiting
  sent: 'info',
  'quotation sent': 'info',
  'contract sent': 'info',
  in_progress: 'info',
  'in progress': 'info',
  assigned: 'info',
  pending: 'info',
  // renewed is good news that also points to a newer record
  renewed: 'primary',
  // needs attention soon
  expiring: 'warning',
  'needs renewal': 'warning',
  expired: 'warning',
  'on hold': 'warning',
  high: 'warning',
  // problem / lost
  overdue: 'error',
  lost: 'error',
  cancelled: 'error',
  rejected: 'error',
  offline: 'error',
  urgent: 'error',
  refunded: 'error',
  // not started / neutral
  draft: 'default',
  new: 'default',
  contacted: 'default',
  inactive: 'default',
  closed: 'default',
  no_device: 'default',
  'to do': 'default',
  low: 'default',
  medium: 'default',
};

export const statusTone = (value?: string | null): StatusTone =>
  (value ? TONES[value.trim().toLowerCase()] : undefined) || 'default';

/** Turns API values such as "in_progress" into "In progress" for display. */
export const humanize = (value?: string | null): string => {
  if (!value) return '';
  const text = value.replace(/_/g, ' ').trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
};
