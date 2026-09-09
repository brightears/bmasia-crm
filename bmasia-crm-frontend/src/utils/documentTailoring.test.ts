import { documentLineTax, documentValidationMessage, effectiveBillingEntity, issuerPaymentTerms } from './documentTailoring';

test('an explicitly chosen Thailand issuer wins for a Hong Kong customer', () => {
  expect(effectiveBillingEntity('BMAsia (Thailand) Co., Ltd.', 'BMAsia Limited')).toBe('BMAsia (Thailand) Co., Ltd.');
  expect(issuerPaymentTerms(effectiveBillingEntity('BMAsia (Thailand) Co., Ltd.', 'BMAsia Limited'))).toContain('TMB-Thanachart');
});

test('blank override inherits the company entity, never a guessed country or currency', () => {
  expect(effectiveBillingEntity('', 'BMAsia Limited')).toBe('BMAsia Limited');
  expect(effectiveBillingEntity('', '')).toBe('');
  expect(issuerPaymentTerms('Thailand')).toBe('');
  expect(issuerPaymentTerms('USD')).toBe('');
});

test('Hong Kong issuer uses Hong Kong payment wording', () => {
  expect(issuerPaymentTerms('BMAsia Limited')).toContain('HSBC Bank, Hong Kong');
});

test('mixed line taxes retain explicit zero and round each line to cents', () => {
  expect(documentLineTax([
    { quantity: 1, unit_price: 100, tax_rate: 0 },
    { quantity: 1, unit_price: 0.11, tax_rate: 7 },
    { quantity: 1, unit_price: 0.11, tax_rate: 7 },
  ])).toBe(0.02);
});

test('nested validation details stay actionable instead of becoming object Object', () => {
  expect(documentValidationMessage({
    error: 'clarification_required', blockers: [{ code: 'missing_payment_slot', action: 'Select a template with an editable payment slot.' }],
  }, 'Failed')).toContain('action: Select a template with an editable payment slot.');
});
