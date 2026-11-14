import { formatMoney } from '../theme/format';
export const ENTITY_CURRENCY: Record<string, { currency: string; locale: string }> = {
  'BMAsia Limited': { currency: 'USD', locale: 'en-US' },
  'BMAsia (Thailand) Co., Ltd.': { currency: 'THB', locale: 'th-TH' },
};

export type EntityFilter = 'BMAsia Limited' | 'BMAsia (Thailand) Co., Ltd.';

export type ServiceFilter = 'all' | 'soundtrack' | 'beatbreeze';

export const ENTITY_OPTIONS: { value: EntityFilter; label: string }[] = [
  { value: 'BMAsia Limited', label: 'BMAsia Ltd (USD)' },
  { value: 'BMAsia (Thailand) Co., Ltd.', label: 'BMAsia Thai (THB)' },
];

export const SERVICE_OPTIONS: { value: ServiceFilter; label: string }[] = [
  { value: 'all', label: 'All Services' },
  { value: 'soundtrack', label: 'Soundtrack' },
  { value: 'beatbreeze', label: 'Beat Breeze' },
];

export const DEFAULT_ENTITY: EntityFilter = 'BMAsia Limited';

/** The currency a billing entity invoices in (THB for the Thai company, otherwise USD). */
export function currencyForEntity(entity?: string | null): string {
  return (entity && ENTITY_CURRENCY[entity]?.currency) || 'USD';
}

/** An amount in the billing entity's currency, written the CRM's way: "THB 108,000". */
export function formatCurrency(value: number, entity?: string): string {
  const n = Number(value ?? 0);
  // Something that is not a number shows as a dash, never as a false 0.
  return formatMoney(Number.isNaN(n) ? null : Math.round(n), currencyForEntity(entity));
}

export function getServiceLabel(serviceType?: string | null): string {
  if (serviceType === 'soundtrack') return 'Soundtrack';
  if (serviceType === 'beatbreeze') return 'Beat Breeze';
  return '-';
}
