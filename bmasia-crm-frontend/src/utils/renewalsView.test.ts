import type { RenewalRow } from '../services/renewals';
import {
  csvCell,
  filterRows,
  parseStates,
  relativeDays,
  rowsToCsv,
  sortRows,
  summarize,
} from './renewalsView';

const row = (over: Partial<RenewalRow> & { state?: RenewalRow['renewal']['state']; group?: RenewalRow['renewal']['group'] } = {}): RenewalRow => {
  const { state = 'not_started', group = 'open', ...rest } = over;
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
    lifecycle_type: '',
    status: 'Active',
    auto_renew: false,
    billing_frequency: 'Annual',
    property_name: '',
    contract_type: 'Annual',
    start_date: '2025-12-01',
    term_months: 12,
    entity: 'hk',
    owner: null,
    owner_source: null,
    days_from_end: -12,
    renewal: {
      state,
      label: state,
      group,
      reason: '',
      attention: null,
      attention_label: null,
      successor: null,
      other_linked: [],
      value_change: null,
      value_change_basis: null,
    },
    ...rest,
  } as RenewalRow;
};

describe('summarize', () => {
  it('keeps every currency apart and computes the renewal rate without auto-renewals', () => {
    const rows = [
      row({ currency: 'THB', value: 108000, state: 'paid', group: 'renewed' }),
      row({ currency: 'THB', value: 50000, state: 'not_started', group: 'open' }),
      row({ currency: 'THB', value: 20000, state: 'lost', group: 'lost' }),
      row({ currency: 'THB', value: 10000, state: 'auto_renews', group: 'auto' }),
      row({ currency: 'USD', value: 1200, state: 'sent', group: 'open' }),
    ];
    const [thb, usd] = summarize(rows);
    expect(thb).toMatchObject({
      currency: 'THB',
      terms: 4,
      value: 188000,
      renewed: 1,
      renewedValue: 108000,
      open: 1,
      atRiskValue: 50000,
      lost: 1,
      lostValue: 20000,
      auto: 1,
      autoValue: 10000,
    });
    expect(thb.rate).toBeCloseTo(1 / 3);
    expect(usd).toMatchObject({ currency: 'USD', terms: 1, value: 1200, atRiskValue: 1200, rate: 0 });
  });

  it('has no rate when every term auto-renews', () => {
    expect(summarize([row({ state: 'auto_renews', group: 'auto' })])[0].rate).toBeNull();
    expect(summarize([])).toEqual([]);
  });
});

describe('filterRows', () => {
  const rows = [
    row({ company: 'Lumen Bay Résort', contract_number: 'TH-CT99001', product: 'Beat Breeze', state: 'sent' }),
    row({ company: 'Harbour Hotel', contract_number: 'HK-CT99002', property_name: 'Harbour Lounge', state: 'paid', group: 'renewed' }),
    row({
      company: 'Quiet Inn',
      contract_number: 'HK-CT99003',
      renewal: { ...row().renewal, attention: 'ended_nothing_sent', attention_label: 'Ended, no renewal sent' },
    }),
  ];
  const none = { states: [], attentionOnly: false, product: '' as const, search: '' };

  it('searches customer, property and contract number, ignoring accents and case', () => {
    expect(filterRows(rows, { ...none, search: 'lumen bay resort' })).toHaveLength(1);
    expect(filterRows(rows, { ...none, search: 'lounge' })).toHaveLength(1);
    expect(filterRows(rows, { ...none, search: 'ct99003' })).toHaveLength(1);
  });

  it('filters by states, product and attention', () => {
    expect(filterRows(rows, { ...none, states: ['sent', 'paid'] })).toHaveLength(2);
    expect(filterRows(rows, { ...none, product: 'Beat Breeze' })).toHaveLength(1);
    expect(filterRows(rows, { ...none, attentionOnly: true }).map((r) => r.company)).toEqual(['Quiet Inn']);
  });
});

describe('parseStates', () => {
  it('keeps known keys only', () => {
    expect(parseStates('sent,bogus,paid')).toEqual(['sent', 'paid']);
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

  it('writes one line per row with a header and a byte order mark', () => {
    const csv = rowsToCsv([row({ company: '=Evil Hotel', value: 108000, currency: 'THB' })]);
    expect(csv.startsWith('﻿Customer,')).toBe(true);
    const lines = csv.trim().split('\r\n');
    expect(lines).toHaveLength(2);
    expect(lines[1].startsWith("'=Evil Hotel,")).toBe(true);
    expect(lines[1]).toContain(',THB,108000,');
  });
});
