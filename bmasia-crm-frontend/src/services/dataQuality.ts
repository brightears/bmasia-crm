import { authApi } from './authService';

/** Read-only data-quality checks (server: crm_app/data_quality.py, /api/v1/data-quality/). */

export type DataQualitySeverity = 'high' | 'medium' | 'low';
export type DataQualityRecordType = 'contract' | 'company' | 'contact' | 'quote' | 'invoice' | 'task';

export interface DataQualityRow {
  id: string;
  record_type: DataQualityRecordType;
  label: string;
  company_id: string | null;
  company_name: string | null;
  /** The sentence that put the record on the list, e.g. "Ended 23 days ago (26 Oct 2026)". */
  fact: string;
  owner_id: string | null;
  owner_name: string | null;
  date: string | null;
  amount: string | null;
  currency: string | null;
  /** Frontend path of the record itself. */
  link: string;
  /** Further records the row stands for (duplicate emails, lookalike names). */
  related: { label: string; link: string }[];
}

export interface DataQualityCheckSummary {
  key: string;
  title: string;
  why: string;
  severity: DataQualitySeverity;
  record_type: DataQualityRecordType;
  count: number;
  rows: DataQualityRow[];
}

export interface DataQualitySummary {
  today: string;
  generated_at: string;
  checks: DataQualityCheckSummary[];
  total: number;
  clear: number;
}

export interface DataQualityCheckPage extends Omit<DataQualityCheckSummary, 'rows'> {
  today: string;
  page: number;
  page_size: number;
  rows: DataQualityRow[];
}

export interface DataQualityFilters {
  company?: string;
  /** A user id, or "none" for rows without an owner. */
  owner?: string;
}

const clean = (params: Record<string, string | number | undefined>) =>
  Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== ''));

export const SEVERITY_LABEL: Record<DataQualitySeverity, string> = { high: 'High', medium: 'Medium', low: 'Low' };
export const SEVERITY_TONE: Record<DataQualitySeverity, 'error' | 'warning' | 'default'> = {
  high: 'error',
  medium: 'warning',
  low: 'default',
};

export async function getDataQualitySummary(rows = 0): Promise<DataQualitySummary> {
  const response = await authApi.get<DataQualitySummary>('/data-quality/', { params: { rows } });
  return response.data;
}

export async function getDataQualityCheck(
  key: string,
  { page = 1, pageSize = 25, ...filters }: DataQualityFilters & { page?: number; pageSize?: number } = {}
): Promise<DataQualityCheckPage> {
  const response = await authApi.get<DataQualityCheckPage>(`/data-quality/${encodeURIComponent(key)}/`, {
    params: clean({ page, page_size: pageSize, company: filters.company, owner: filters.owner }),
  });
  return response.data;
}

/** Downloads every row of one check as CSV (with the user's sign-in, so not a plain link). */
export async function downloadDataQualityCsv(key: string, filters: DataQualityFilters = {}): Promise<void> {
  const response = await authApi.get(`/data-quality/${encodeURIComponent(key)}/`, {
    params: clean({ export: 'csv', company: filters.company, owner: filters.owner }),
    responseType: 'blob',
  });
  const disposition: string = response.headers?.['content-disposition'] || '';
  const name = /filename="([^"]+)"/.exec(disposition)?.[1] || `needs-fixing-${key}.csv`;
  const url = window.URL.createObjectURL(new Blob([response.data], { type: 'text/csv' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
