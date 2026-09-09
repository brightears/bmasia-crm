export const DOCUMENT_BILLING_ENTITIES = [
  'BMAsia (Thailand) Co., Ltd.',
  'BMAsia Limited',
] as const;

export type DocumentBillingEntity = typeof DOCUMENT_BILLING_ENTITIES[number] | '';

/** A document override wins. Neither customer country nor currency chooses the issuer. */
export function effectiveBillingEntity(override?: string, companyEntity?: string): string {
  return override || companyEntity || '';
}

const PAYMENT_TERMS: Record<string, string> = {
  'BMAsia (Thailand) Co., Ltd.': "by bank transfer on a net received, paid in full basis, with no offset to BMA's TMB-Thanachart Bank, Bangkok, Thailand due immediately on invoicing to activate the music subscription. All outbound and inbound bank transfer fees are borne by the Client in remitting payments as invoiced less Withholding Tax required by Thai Law.",
  'BMAsia Limited': "by bank transfer on a net received, paid in full basis, with no offset to BMA's HSBC Bank, Hong Kong due immediately as invoiced to activate the music subscription. All Bank transfer fees, and all taxes are borne by the Client in remitting payments as invoiced.",
};

export function issuerPaymentTerms(entity: string): string {
  return PAYMENT_TERMS[entity] || '';
}

export function documentLineTax(items: Array<{ quantity: number; unit_price: number; tax_rate: number }>): number {
  const cents = items.reduce((sum, item) => sum + Math.round((item.quantity * item.unit_price * item.tax_rate / 100 + Number.EPSILON) * 100), 0);
  return cents / 100;
}

/** Keep validation and clarification actionable, including nested DRF field errors. */
export function documentValidationMessage(payload: unknown, fallback: string): string {
  if (!payload) return fallback;
  if (typeof payload === 'string') return payload;
  if (Array.isArray(payload)) return payload.map(item => documentValidationMessage(item, '')).filter(Boolean).join('; ') || fallback;
  if (typeof payload === 'object') {
    return Object.entries(payload as Record<string, unknown>)
      .map(([field, value]) => {
        const message = documentValidationMessage(value, '');
        return message ? `${field}: ${message}` : '';
      })
      .filter(Boolean).join('; ') || fallback;
  }
  return String(payload);
}
