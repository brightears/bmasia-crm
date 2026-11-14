import { ContractZone } from '../types';

interface TermLike {
  start_date?: string | null;
  end_date?: string | null;
  contract_zones?: ContractZone[];
}

/**
 * Zone links that covered any part of the contract's term: the link started on
 * or before the term's end and has no end date or ended on or after the term's
 * start, whether or not it is active today. One link per zone (the latest
 * start). Matches Contract.get_term_links on the server, so a Renewed term whose
 * links were handed over to its renewal, or a Cancelled term, still shows the
 * zones it covered.
 */
export function linksCoveringTerm(contract: TermLike | null | undefined): ContractZone[] {
  const links = contract?.contract_zones || [];
  const start = contract?.start_date || null;
  const end = contract?.end_date || null;
  const covering = links.filter((link) => {
    if (end && link.start_date && link.start_date > end) return false;
    if (start && link.end_date && link.end_date < start) return false;
    return true;
  });
  const byZone = new Map<string, ContractZone>();
  covering.forEach((link) => {
    const key = link.zone_id || link.zone || link.id;
    const seen = byZone.get(key);
    if (!seen || (link.start_date || '') > (seen.start_date || '')) {
      byZone.set(key, link);
    }
  });
  return Array.from(byZone.values());
}
