import { moneyLines, negativeMoneyLines, revenueChange, trendCurrencies, trendSeries } from './dashboardMoney';

const TH = 'BMAsia (Thailand) Co., Ltd.';

describe('moneyLines', () => {
  it('older response: the single total in the entity currency, as before', () => {
    expect(moneyLines(undefined, 110160, TH)).toEqual(['THB 110,160']);
  });
  it('per currency: one line each, the entity currency first, never added together', () => {
    expect(
      moneyLines([{ currency: 'USD', total: '2160.00' }, { currency: 'THB', total: '108000.00' }], 110160, TH)
    ).toEqual(['THB 108,000', 'USD 2,160']);
  });
  it('per currency with nothing: zero in the entity currency', () => {
    expect(moneyLines([], 0, TH)).toEqual(['THB 0']);
  });
  it('the entity currency always shows, as 0 when it has nothing', () => {
    expect(moneyLines([{ currency: 'USD', total: '2160.00' }], 2160, TH)).toEqual(['THB 0', 'USD 2,160']);
  });
  it('older response with decimals as text', () => {
    expect(moneyLines(undefined, '110160.00' as any, TH)).toEqual(['THB 110,160']);
  });
  it('churn gets a minus sign on non-zero lines', () => {
    expect(negativeMoneyLines([{ currency: 'USD', total: '500.00' }], 500, TH)).toEqual(['THB 0', '-USD 500']);
    expect(negativeMoneyLines(undefined, 0, TH)).toEqual(['THB 0']);
  });
});

describe('revenueChange', () => {
  it('older response compares the totals', () => {
    expect(revenueChange({ total: 150 }, { total: 100 }, TH)).toEqual({ value: 50, label: 'vs last month' });
  });
  it('a previous month of "0.00" (text, as the API sends it) gives 0, not Infinity', () => {
    expect(revenueChange({ total: '2160.00' as any }, { total: '0.00' as any }, TH).value).toBe(0);
  });
  it('per currency compares the entity currency only and says so when others exist', () => {
    const r = revenueChange(
      { total: 0, byCurrency: [{ currency: 'THB', total: '120' }, { currency: 'USD', total: '999' }] },
      { total: 0, byCurrency: [{ currency: 'THB', total: '100' }] },
      TH
    );
    expect(r.value).toBeCloseTo(20);
    expect(r.label).toBe('vs last month (THB only)');
  });
});

describe('trend', () => {
  const trend: any[] = [
    { month: 'Oct', revenue: 1, by_currency: [{ currency: 'USD', revenue: '10', new_revenue: '10', renewal_revenue: '0', churned_revenue: '0', net_revenue: '10' }] },
    { month: 'Nov', revenue: 2, by_currency: [{ currency: 'THB', revenue: '500', new_revenue: '300', renewal_revenue: '200', churned_revenue: '50', net_revenue: '450' }] },
  ];
  it('lists currencies, entity currency first; none for older responses', () => {
    expect(trendCurrencies(trend, TH)).toEqual(['THB', 'USD']);
    expect(trendCurrencies([{ month: 'Nov', revenue: 2 }], TH)).toEqual([]);
  });
  it('gives one currency series with zeros where a month has none', () => {
    expect(trendSeries(trend, 'THB')).toEqual([
      { month: 'Oct', revenue: 0, new_revenue: 0, renewal_revenue: 0, churned_revenue: 0, net_revenue: 0 },
      { month: 'Nov', revenue: 500, new_revenue: 300, renewal_revenue: 200, churned_revenue: 50, net_revenue: 450 },
    ]);
    expect(trendSeries(trend, null)).toBe(trend);
  });
});
