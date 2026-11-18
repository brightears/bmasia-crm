import {
  TimelineEvent,
  changeSentence,
  dayLabel,
  eventDay,
  eventExactTime,
  eventSummary,
  groupByDay,
  hasMore,
  linkHref,
  relativeTime,
  timelineParams,
} from './timelineModel';

const event = (overrides: Partial<TimelineEvent> = {}): TimelineEvent => ({
  id: 'note:1',
  type: 'note',
  category: 'note',
  occurred_at: new Date(2026, 10, 14, 9, 30).toISOString(),
  precision: 'datetime',
  title: 'Call',
  detail: '',
  actor: null,
  links: [],
  changes: [],
  extra: {},
  ...overrides,
});

const NOW = new Date(2026, 10, 18, 12, 0);

describe('timelineParams', () => {
  it('turns filters into query parameters and leaves out empty ones', () => {
    expect(
      timelineParams({
        types: ['note', 'email'],
        from: '2026-11-01',
        record: { type: 'contract', id: 'c-1' },
        q: '  renewal ',
        cursor: 'abc',
        page_size: 10,
        facets: true,
      })
    ).toEqual({
      types: 'note,email',
      from: '2026-11-01',
      record: 'contract:c-1',
      q: 'renewal',
      cursor: 'abc',
      page_size: '10',
      facets: '1',
    });
    expect(timelineParams({ types: [], q: '   ' })).toEqual({});
  });
});

describe('days', () => {
  it('labels today, yesterday and older days', () => {
    expect(dayLabel('2026-11-18', NOW)).toBe('Today');
    expect(dayLabel('2026-11-17', NOW)).toBe('Yesterday');
    expect(dayLabel('2026-11-14', NOW)).toBe('14 Nov 2026');
  });

  it('keeps the recorded day of date-only events, whatever the viewer time zone', () => {
    const dateOnly = event({ precision: 'date', date: '2026-11-10', occurred_at: '2026-11-09T17:00:00+00:00' });
    expect(eventDay(dateOnly)).toBe('2026-11-10');
    expect(eventExactTime(dateOnly)).toBe('10 Nov 2026 (no time recorded)');
  });

  it('groups consecutive events by day in server order', () => {
    const groups = groupByDay(
      [
        event({ id: 'a', occurred_at: new Date(2026, 10, 18, 11).toISOString() }),
        event({ id: 'b', occurred_at: new Date(2026, 10, 18, 8).toISOString() }),
        event({ id: 'c', occurred_at: new Date(2026, 10, 17, 22).toISOString() }),
        event({ id: 'd', precision: 'date', date: '2026-11-14' }),
      ],
      NOW
    );
    expect(groups.map((g) => [g.label, g.events.map((e) => e.id)])).toEqual([
      ['Today', ['a', 'b']],
      ['Yesterday', ['c']],
      ['14 Nov 2026', ['d']],
    ]);
  });
});

describe('relativeTime', () => {
  it.each([
    [new Date(2026, 10, 18, 11, 59, 30), 'just now'],
    [new Date(2026, 10, 18, 11, 55), '5 min ago'],
    [new Date(2026, 10, 18, 9, 0), '3 h ago'],
    [new Date(2026, 10, 17, 11, 0), '1 day ago'],
    [new Date(2026, 10, 4, 12, 0), '14 days ago'],
    [new Date(2026, 6, 18, 12, 0), '4 months ago'],
    [new Date(2024, 10, 1, 12, 0), '2 years ago'],
  ])('%s → %s', (when, expected) => {
    expect(relativeTime(when.toISOString(), NOW)).toBe(expected);
  });

  it('shows the exact time as "14 Nov 2026, 09:30"', () => {
    expect(eventExactTime(event())).toBe('14 Nov 2026, 09:30');
  });
});

describe('changeSentence', () => {
  it('formats dates, money and empty values with the shared formatters', () => {
    expect(changeSentence({ field: 'end_date', label: 'End date', kind: 'date', old: '2026-12-31', new: '2027-12-31' })).toBe(
      'Changed End date from 31 Dec 2026 to 31 Dec 2027'
    );
    expect(
      changeSentence({ field: 'value', label: 'Value', kind: 'money', old: '100000.00', new: '108000.00', currency: 'THB' })
    ).toBe('Changed Value from THB 100,000 to THB 108,000');
    expect(changeSentence({ field: 'title', label: 'Title', kind: 'text', old: null, new: 'GM' })).toBe(
      'Changed Title from empty to GM'
    );
    expect(changeSentence({ field: 'line_items', label: 'Line items', kind: 'collection', old: null, new: null })).toBe(
      'Changed Line items'
    );
  });
});

describe('links and summaries', () => {
  it('opens each record on its own page; invoices go to their contract or the list', () => {
    expect(linkHref({ type: 'contract', id: 'c', label: 'TH-1' })).toBe('/contracts/c');
    expect(linkHref({ type: 'quote', id: 'q', label: 'QT' })).toBe('/quotes/q');
    expect(linkHref({ type: 'opportunity', id: 'o', label: 'O' })).toBe('/opportunities/o');
    expect(linkHref({ type: 'ticket', id: 't', label: 'T' })).toBe('/tickets/t');
    expect(linkHref({ type: 'invoice', id: 'i', label: 'INV 1', contract_id: 'c' })).toBe('/contracts/c');
    expect(linkHref({ type: 'invoice', id: 'i', label: 'INV 1' })).toBe('/invoices?q=INV%201');
    expect(linkHref({ type: 'contact', id: 'p', label: 'Pat' })).toBeNull();
  });

  it('summarises money, email type and assignment', () => {
    expect(eventSummary(event({ category: 'contract', extra: { money: { amount: '108000.00', currency: 'THB' } } }))).toBe(
      'THB 108,000'
    );
    expect(eventSummary(event({ type: 'task_created', category: 'task', extra: { assigned_to: 'Sam' } }))).toBe(
      'Assigned to Sam'
    );
    expect(eventSummary(event())).toBeNull();
  });

  it('only offers details when there is something to show', () => {
    expect(hasMore(event())).toBe(false);
    expect(hasMore(event({ detail: 'Spoke to the GM' }))).toBe(false); // short detail is shown as it is
    expect(hasMore(event({ detail: 'x'.repeat(200) }))).toBe(true);
    expect(hasMore(event({ detail: 'one\ntwo\nthree' }))).toBe(true);
    expect(hasMore(event({ changes: [{ field: 'x', label: 'X', kind: 'text', old: 'a', new: 'b' }] }))).toBe(true);
  });
});
