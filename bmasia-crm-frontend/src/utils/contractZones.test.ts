import { documentZoneLinks, linksCoveringTerm } from './contractZones';
import { ContractZone } from '../types';

const link = (id: string, zone: string, start: string, end: string | null, active: boolean): ContractZone => ({
  id, contract: 'c', zone, zone_id: zone, zone_name: `Zone ${zone}`, start_date: start, end_date: end,
  is_active: active, created_at: '', updated_at: '',
} as ContractZone);

describe('linksCoveringTerm', () => {
  const term = { start_date: '2025-01-01', end_date: '2025-12-31' };

  it('keeps links handed over at the end of the term', () => {
    const links = [link('1', 'a', '2025-01-01', '2025-12-31', false), link('2', 'b', '2025-01-01', null, true)];
    expect(linksCoveringTerm({ ...term, contract_zones: links }).map((l) => l.id)).toEqual(['1', '2']);
  });

  it('drops links outside the term', () => {
    const links = [link('1', 'a', '2024-01-01', '2024-12-31', false), link('2', 'b', '2026-01-01', null, true)];
    expect(linksCoveringTerm({ ...term, contract_zones: links })).toEqual([]);
  });

  it('counts a zone once', () => {
    const links = [link('1', 'a', '2025-01-01', '2025-06-30', false), link('2', 'a', '2025-07-01', null, true)];
    expect(linksCoveringTerm({ ...term, contract_zones: links }).map((l) => l.id)).toEqual(['2']);
  });

  it('treats an open term as no limit', () => {
    const links = [link('1', 'a', '2030-01-01', null, true)];
    expect(linksCoveringTerm({ start_date: '2025-01-01', end_date: null, contract_zones: links })).toHaveLength(1);
    expect(linksCoveringTerm(null)).toEqual([]);
  });
});

describe('documentZoneLinks', () => {
  const links = [link('1', 'a', '2025-01-01', '2025-03-31', false), link('2', 'b', '2025-04-01', null, true)];

  it('uses the whole term for an ended term', () => {
    const contract = { status: 'Renewed', start_date: '2025-01-01', end_date: '2025-12-31', contract_zones: links };
    expect(documentZoneLinks(contract).map((l) => l.id)).toEqual(['1', '2']);
  });

  it('uses the links open today for a live contract', () => {
    const contract = { status: 'Active', start_date: '2025-01-01', end_date: '2025-12-31', contract_zones: links };
    expect(documentZoneLinks(contract).map((l) => l.id)).toEqual(['2']);
  });
});
