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

export function formatCurrency(value: number, entity?: string): string {
  const config = entity ? ENTITY_CURRENCY[entity] : undefined;
  const currency = config?.currency || 'USD';
  const locale = config?.locale || 'en-US';
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

export function getServiceLabel(serviceType?: string | null): string {
  if (serviceType === 'soundtrack') return 'Soundtrack';
  if (serviceType === 'beatbreeze') return 'Beat Breeze';
  return '-';
}
