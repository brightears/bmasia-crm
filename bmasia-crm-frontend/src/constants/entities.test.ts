import { currencyForEntity, formatCurrency } from './entities';

describe('entity currency', () => {
  it('uses THB for the Thai company and USD otherwise', () => {
    expect(currencyForEntity('BMAsia (Thailand) Co., Ltd.')).toBe('THB');
    expect(currencyForEntity('BMAsia Limited')).toBe('USD');
    expect(currencyForEntity(undefined)).toBe('USD');
  });

  it('formats whole amounts with the currency code first, and never shows a bad value as 0', () => {
    expect(formatCurrency(108000.4, 'BMAsia (Thailand) Co., Ltd.')).toBe('THB 108,000');
    expect(formatCurrency('4450.00' as any, 'BMAsia Limited')).toBe('USD 4,450');
    expect(formatCurrency(NaN, 'BMAsia Limited')).toBe('—');
  });
});
