import { createAppTheme, formatDate, formatMoney, humanize, statusTone, totalsByCurrency } from '.';

describe('statusTone', () => {
  it('maps statuses to one colour language regardless of case or spacing', () => {
    expect(statusTone('Active')).toBe('success');
    expect(statusTone(' paid ')).toBe('success');
    expect(statusTone('Quotation Sent')).toBe('info');
    expect(statusTone('in_progress')).toBe('info');
    expect(statusTone('Overdue')).toBe('error');
    expect(statusTone('Expired')).toBe('warning');
    expect(statusTone('Draft')).toBe('default');
  });

  it('falls back to neutral for unknown or empty values', () => {
    expect(statusTone('something new')).toBe('default');
    expect(statusTone(undefined)).toBe('default');
    expect(statusTone(null)).toBe('default');
  });
});

describe('display formats', () => {
  it('humanizes API values', () => {
    expect(humanize('in_progress')).toBe('In progress');
    expect(humanize('no_device')).toBe('No device');
    expect(humanize('')).toBe('');
  });

  it('formats dates the same way everywhere', () => {
    expect(formatDate('2026-11-14')).toBe('14 Nov 2026');
    expect(formatDate(null)).toBe('—');
    expect(formatDate('not a date')).toBe('—');
  });

  it('puts the currency code first and drops .00', () => {
    expect(formatMoney(108000, 'THB')).toBe('THB 108,000');
    expect(formatMoney('720.50', 'USD')).toBe('USD 720.50');
    expect(formatMoney(undefined)).toBe('—');
  });
});

describe('totalsByCurrency', () => {
  it('never adds different currencies together', () => {
    expect(
      totalsByCurrency([
        { amount: 108000, currency: 'THB' },
        { amount: '4450.50', currency: 'USD' },
        { amount: 2000, currency: 'THB' },
        { amount: 100, currency: null },
      ])
    ).toEqual([
      ['THB', 110000],
      ['USD', 4550.5],
    ]);
    expect(totalsByCurrency([])).toEqual([]);
  });
});

describe('createAppTheme', () => {
  it('builds light and dark themes with the BMAsia font and colours', () => {
    const light = createAppTheme('light');
    const dark = createAppTheme('dark');
    expect(light.palette.mode).toBe('light');
    expect(dark.palette.mode).toBe('dark');
    expect(String(light.typography.fontFamily)).toContain('Geist');
    expect(light.palette.primary.main).toBe('#A86A12');
    expect(dark.palette.primary.main).toBe('#EFA634');
  });
});
