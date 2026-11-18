import type { RenewalRow } from '../services/renewals';
import { csvCell, CSV_HEADER, filterRows, parseStates, relativeDays, rowsToCsv, sortRows, summarize } from './renewalsView';

type Over = Partial<RenewalRow> & {
  state?: RenewalRow['renewal']['state'];
  bucket?: RenewalRow['renewal']['summary_bucket'];
  inRate?: boolean;
  successor?: Partial<NonNullable<RenewalRow['renewal']['successor']>>;
  change?: number | null;
};

const row = (over: Over = {}): RenewalRow => {
  const { state = 'not_started', bucket = 'open', inRate = false, successor, change = null, ...rest } = over;
  return {
    contract_id: `c-${Math.random()}`,
    company_id: 'co-1',
    contract_number: 'HK-CT99001',
    corporate_group: 'Fixture Group',
    company: 'Fixture Resort',
    country: 'Thailand',
    end_date: '2026-11-30',
    zones: 2,
    zones_source: 'service_locations',
    value: 1200,
    currency: 'USD',
    product: 'Soundtrack',
    product_display: 'Soundtrack',
    product_source: 'renewal_book',
    lifecycle_type: '',
    status: 'Active',
    auto_renew: false,
    billing_frequency: 'Annual',
    book: { successor_contract: null, successor_status: null, invoices_paid: false, outstanding_amount: 0 },
    property_name: '',
    contract_type: 'Annual',
    start_date: '2025-12-01',
    term_months: 12,
    entity: 'hk',
    owner: null,
    owner_source: null,
    days_from_end: -12,
    is_addon: false,
    never_activated: false,
    renewal: {
      state,
      label: state,
      group: bucket,
      summary_bucket: bucket,
      in_rate: inRate,
      reason: '',
      attention: null,
      attention_label: null,
      successor: successor
        ? ({
            contract_id: 's-1',
            contract_number: 'HK-CT99100',
            status: 'Active',
            start_date: '2026-12-01',
            end_date: '2027-11-30',
            term_months: 12,
            value: 1200,
            currency: 'USD',
            signed_date: null,
            sent_date: null,
            invoice_state: 'none',
            other_company: false,
            ...successor,
          } as RenewalRow['renewal']['successor'])
        : null,
      other_linked: [],
      value_change: change,
      value_change_basis: change === null ? null : 'term',
    },
    ...rest,
  } as RenewalRow;
};

describe('summarize', () => {
  it('keeps every currency apart; renewed money is the renewals; the rate uses decided or ended terms', () => {
    const rows = [
      row({ currency: 'THB', value: 108000, state: 'paid', bucket: 'renewed', inRate: true,
            successor: { value: 120000, currency: 'THB' } }),
      row({ currency: 'THB', value: 50000, state: 'not_started', bucket: 'open', inRate: true }),   // ended, open
      row({ currency: 'THB', value: 70000, state: 'not_started', bucket: 'open', inRate: false }),  // still ahead
      row({ currency: 'THB', value: 20000, state: 'lost', bucket: 'lost', inRate: true }),
      row({ currency: 'THB', value: 10000, state: 'auto_renews', bucket: 'auto' }),
      row({ currency: 'THB', value: 9000, state: 'placeholder', bucket: 'excluded' }),            // counts nowhere
      row({ currency: 'THB', value: 8000, state: 'lost', bucket: 'excluded', never_activated: true }),
      row({ currency: 'USD', value: 1200, state: 'sent', bucket: 'open' }),
    ];
    const [thb, usd] = summarize(rows);
    expect(thb).toMatchObject({
      currency: 'THB',
      terms: 6,
      value: 266000,
      renewed: 1,
      renewedValue: 120000,
      open: 2,
      atRiskValue: 120000,
      lost: 1,
      lostValue: 20000,
      auto: 1,
      rateBase: 3,
      rateRenewed: 1,
    });
    expect(thb.rate).toBeCloseTo(1 / 3);
    expect(usd).toMatchObject({ currency: 'USD', terms: 1, atRiskValue: 1200, rate: null });
  });

  it('adds a renewal in another currency to that currency', () => {
    const [thb, usd] = summarize([
      row({ currency: 'USD', value: 3000, state: 'signed', bucket: 'renewed', inRate: true,
            successor: { value: 110000, currency: 'THB' } }),
    ]);
    expect(thb).toMatchObject({ currency: 'THB', terms: 0, renewedValue: 110000 });
    expect(usd).toMatchObject({ currency: 'USD', terms: 1, renewed: 1, renewedValue: 0, rate: 1 });
  });

  it('has no rate while nothing is decided', () => {
    expect(summarize([row({ state: 'not_started', bucket: 'open' })])[0].rate).toBeNull();
    expect(summarize([])).toEqual([]);
  });
});

describe('filterRows', () => {
  const rows = [
    row({ company: 'Lumen Bay Résort', contract_number: 'TH-CT99001', product: 'Beat Breeze', product_display: 'Beat Breeze', state: 'sent' }),
    row({ company: 'Mixed Hall', contract_number: 'TH-CT99004', product: 'Other', product_display: 'Beat Breeze + Soundtrack', product_source: 'service_locations' }),
    row({ company: 'Harbour Hotel', contract_number: 'HK-CT99002', property_name: 'Harbour Lounge', state: 'paid', bucket: 'renewed' }),
    row({
      company: 'Quiet Inn',
      contract_number: 'HK-CT99003',
      renewal: { ...row().renewal, attention: 'ended_nothing_sent', attention_label: 'Ended, no renewal sent' },
    }),
    row({ company: 'Old Placeholder', contract_number: 'HK-CT99005', state: 'placeholder', bucket: 'excluded' }),
    row({ company: 'Offer Only', contract_number: 'HK-CT99006', never_activated: true }),
  ];
  const none = { states: [], attentionOnly: false, product: '' as const, search: '' };

  it('searches customer, property and contract number, ignoring accents and case', () => {
    expect(filterRows(rows, { ...none, search: 'lumen bay resort' })).toHaveLength(1);
    expect(filterRows(rows, { ...none, search: 'lounge' })).toHaveLength(1);
    expect(filterRows(rows, { ...none, search: 'ct99003' })).toHaveLength(1);
  });

  it('filters by states, product and attention', () => {
    expect(filterRows(rows, { ...none, states: ['sent', 'paid'] })).toHaveLength(2);
    expect(filterRows(rows, { ...none, product: 'Beat Breeze' }).map((r) => r.company)).toEqual(['Lumen Bay Résort', 'Mixed Hall']);
    expect(filterRows(rows, { ...none, product: 'Soundtrack' })).toHaveLength(4);
    expect(filterRows(rows, { ...none, product: 'Other' })).toHaveLength(0);
    expect(filterRows(rows, { ...none, attentionOnly: true }).map((r) => r.company)).toEqual(['Quiet Inn']);
  });

  it('hides placeholders unless asked, and can show only never-activated terms', () => {
    expect(filterRows(rows, none).map((r) => r.company)).not.toContain('Old Placeholder');
    expect(filterRows(rows, { ...none, showPlaceholders: true }).map((r) => r.company)).toContain('Old Placeholder');
    expect(filterRows(rows, { ...none, neverActivatedOnly: true }).map((r) => r.company)).toEqual(['Offer Only']);
  });
});

describe('parseStates', () => {
  it('keeps known keys only', () => {
    expect(parseStates('sent,bogus,paid,part_paid')).toEqual(['sent', 'paid', 'part_paid']);
    expect(parseStates('')).toEqual([]);
  });
});

describe('sortRows', () => {
  const a = row({ company: 'Alpha', value: 300, end_date: '2026-11-20' });
  const b = row({ company: 'beta', value: 100, end_date: '2026-11-05' });
  const c = row({ company: 'Gamma', value: 200, end_date: '2026-11-12', owner: 'Robin' });

  it('keeps the server order by default', () => {
    expect(sortRows([b, a, c], '')).toEqual([b, a, c]);
  });

  it('sorts both ways on a column, empty values last', () => {
    expect(sortRows([a, b, c], 'value').map((r) => r.company)).toEqual(['beta', 'Gamma', 'Alpha']);
    expect(sortRows([a, b, c], '-value').map((r) => r.company)).toEqual(['Alpha', 'Gamma', 'beta']);
    expect(sortRows([a, b, c], 'company').map((r) => r.company)).toEqual(['Alpha', 'beta', 'Gamma']);
    expect(sortRows([a, b, c], 'end').map((r) => r.company)).toEqual(['beta', 'Gamma', 'Alpha']);
    expect(sortRows([a, b, c], 'owner').map((r) => r.company)).toEqual(['Gamma', 'Alpha', 'beta']);
    expect(sortRows([a, b, c], '-owner').map((r) => r.company)).toEqual(['Gamma', 'Alpha', 'beta']);
  });

  it('sorts numbers as numbers, not text', () => {
    const small = row({ company: 'Small', value: 900 });
    const big = row({ company: 'Big', value: 1200 });
    expect(sortRows([big, small], 'value').map((r) => r.company)).toEqual(['Small', 'Big']);
    const z9 = row({ company: 'Nine', zones: 9 });
    const z12 = row({ company: 'Twelve', zones: 12 });
    expect(sortRows([z12, z9], 'zones').map((r) => r.company)).toEqual(['Nine', 'Twelve']);
  });

  it('sorts money by currency first, then amount, both ways', () => {
    const thb = row({ company: 'Baht', value: 20000, currency: 'THB', change: 500 });
    const usd = row({ company: 'Dollar', value: 5000, currency: 'USD', change: -100 });
    const usd2 = row({ company: 'Dollar small', value: 900, currency: 'USD', change: 50 });
    expect(sortRows([usd, thb, usd2], 'value').map((r) => r.company)).toEqual(['Baht', 'Dollar small', 'Dollar']);
    expect(sortRows([usd2, thb, usd], '-value').map((r) => r.company)).toEqual(['Baht', 'Dollar', 'Dollar small']);
    expect(sortRows([usd, thb, usd2], 'change').map((r) => r.company)).toEqual(['Baht', 'Dollar', 'Dollar small']);
  });
});

describe('relativeDays', () => {
  it('reads naturally', () => {
    expect(relativeDays(-12)).toBe('in 12 days');
    expect(relativeDays(0)).toBe('today');
    expect(relativeDays(1)).toBe('1 day ago');
    expect(relativeDays(null)).toBe('');
  });
});

describe('CSV', () => {
  it('neutralises cells a spreadsheet would run as a formula', () => {
    expect(csvCell('=HYPERLINK("http://example.invalid")')).toBe(`"'=HYPERLINK(""http://example.invalid"")"`);
    expect(csvCell('+1 555')).toBe("'+1 555");
    expect(csvCell('-cmd')).toBe("'-cmd");
    expect(csvCell('@SUM(A1)')).toBe("'@SUM(A1)");
    expect(csvCell('\tTab')).toBe("'\tTab");
    expect(csvCell(-200)).toBe('-200');
    expect(csvCell('Plain, with comma')).toBe('"Plain, with comma"');
    expect(csvCell(null)).toBe('');
    expect(csvCell(true)).toBe('yes');
  });

  it('writes one line per row with a header that states the sign of days from end', () => {
    expect(CSV_HEADER).toContain('Days from end (positive = ended, negative = days to go)');
    const csv = rowsToCsv([row({ company: '=Evil Hotel', value: 108000, currency: 'THB' })]);
    expect(csv.startsWith('﻿Customer,')).toBe(true);
    const lines = csv.trim().split('\r\n');
    expect(lines).toHaveLength(2);
    expect(lines[1].startsWith("'=Evil Hotel,")).toBe(true);
    expect(lines[1]).toContain(',THB,108000,');
  });
});
