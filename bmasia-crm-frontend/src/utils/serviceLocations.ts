/**
 * Service-location rows in the contract form.
 *
 * A contract's service-location rows (one per zone) drive its zone count and the PDF zone table.
 * The form derives *new* rows from music line items, but saved rows must never disappear as a side
 * effect of opening and saving a contract:
 *  - on load the saved rows are shown as they are (no re-derivation from line items);
 *  - a line-item change only re-derives the product groups whose required count changed, and only
 *    by the size of that change (rows imported or back-filled without line items are left alone);
 *  - the save payload carries rows only when they changed in this session, and names every saved
 *    row it removes in `remove_service_location_ids` (the API refuses any other deletion).
 */

export type LocationPlatform = 'soundtrack' | 'beatbreeze' | 'custom';

export interface ServiceLocationEntry {
  id?: string;
  location_name: string;
  platform: LocationPlatform;
  custom_service_name?: string;
  tempId: string;
}

export interface LineItemLike {
  product_service: string;
  quantity: number;
}

/** Maps a line item's product to a platform; null/undefined = not a standard music product. */
export type PlatformLookup = (productService: string) => 'soundtrack' | 'beatbreeze' | null | undefined;

interface Group {
  platform: LocationPlatform;
  custom_service_name?: string;
  required: number;
}

export const groupKey = (loc: { platform: LocationPlatform; custom_service_name?: string }): string =>
  loc.platform === 'custom' ? `custom:${loc.custom_service_name || ''}` : loc.platform;

/** Rows each product group needs according to the line items (same counting rules as before). */
export function requiredGroups(lineItems: LineItemLike[], lookup: PlatformLookup): Map<string, Group> {
  const groups = new Map<string, Group>();
  const add = (platform: LocationPlatform, qty: number, custom?: string) => {
    const key = groupKey({ platform, custom_service_name: custom });
    const g = groups.get(key) || { platform, custom_service_name: custom, required: 0 };
    g.required += Math.max(0, Math.round(qty));
    groups.set(key, g);
  };
  for (const item of lineItems) {
    const platform = lookup(item.product_service);
    if (platform) {
      add(platform, item.quantity);
    } else if (item.product_service && item.quantity > 0) {
      add('custom', item.quantity, item.product_service === 'Custom' ? 'Custom' : item.product_service);
    }
  }
  return groups;
}

/** Required row count per product group, as recorded after the previous sync (or at load). */
export type RequiredCounts = Map<string, number>;

export const requiredCounts = (groups: Map<string, Group>): RequiredCounts =>
  new Map(Array.from(groups.entries()).map(([key, g]) => [key, g.required]));

export const sameCounts = (a: RequiredCounts, b: RequiredCounts): boolean => {
  const keys = new Set([...Array.from(a.keys()), ...Array.from(b.keys())]);
  return Array.from(keys).every(key => (a.get(key) || 0) === (b.get(key) || 0));
};

export interface SyncResult {
  locations: ServiceLocationEntry[];
  /** Saved rows (with an id) dropped so far and not restored; deleted only when the form is saved. */
  parked: ServiceLocationEntry[];
  /** Named rows that were never saved and are dropped now. */
  droppedUnsavedNamedCount: number;
  /** Blank rows added for a quantity increase. */
  addedCount: number;
  /** Parked saved rows put back by a quantity increase. */
  restoredCount: number;
}

/**
 * Re-derive rows after a line-item change, group by group, from the change in each group's
 * required count since the previous sync:
 *  - unchanged group: untouched (whatever its rows vs. its quantity);
 *  - count went up: first put back saved rows parked by an earlier decrease, then add blank rows,
 *    only up to the new count (a group that already has more rows than the new count gets nothing);
 *  - count went down by d: drop at most d rows, never going below the new count; unnamed and unsaved
 *    rows go first, saved named rows last.
 * Groups no line item ever backed are never touched.
 */
export function syncLocationsFromLineItems(
  lineItems: LineItemLike[],
  current: ServiceLocationEntry[],
  lookup: PlatformLookup,
  previous: RequiredCounts,
  newTempId: () => string,
  parkedBefore: ServiceLocationEntry[] = [],
): SyncResult {
  const groups = requiredGroups(lineItems, lookup);
  const order: string[] = [];
  const byGroup = new Map<string, ServiceLocationEntry[]>();
  for (const loc of current) {
    const key = groupKey(loc);
    if (!byGroup.has(key)) {
      byGroup.set(key, []);
      order.push(key);
    }
    byGroup.get(key)!.push(loc);
  }
  for (const key of Array.from(groups.keys())) {
    if (!byGroup.has(key)) {
      byGroup.set(key, []);
      order.push(key);
    }
  }

  const result: ServiceLocationEntry[] = [];
  let parked = [...parkedBefore];
  let droppedUnsavedNamedCount = 0;
  let addedCount = 0;
  let restoredCount = 0;
  for (const key of order) {
    const rows = byGroup.get(key)!;
    const before = previous.get(key) || 0;
    const now = groups.get(key)?.required || 0;
    if (now > before) {
      result.push(...rows);
      const sample = groups.get(key)!;
      let have = rows.length;
      for (const loc of parked.filter(p => groupKey(p) === key)) {
        if (have >= now) break;
        result.push(loc);
        parked = parked.filter(p => p.tempId !== loc.tempId);
        restoredCount += 1;
        have += 1;
      }
      for (let i = have; i < now; i++) {
        addedCount += 1;
        result.push({
          location_name: '', platform: sample.platform, tempId: newTempId(),
          ...(sample.platform === 'custom' ? { custom_service_name: sample.custom_service_name } : {}),
        });
      }
      continue;
    }
    const toDrop = Math.min(before - now, Math.max(0, rows.length - now));
    if (toDrop <= 0) {
      result.push(...rows); // unchanged group, or already at/below the new count
      continue;
    }
    const rank = (loc: ServiceLocationEntry) => (loc.location_name.trim() ? 2 : 0) + (loc.id ? 1 : 0);
    const dropOrder = rows
      .map((loc, index) => ({ loc, index }))
      .sort((a, b) => rank(a.loc) - rank(b.loc) || b.index - a.index);
    const drop = new Set(dropOrder.slice(0, toDrop).map(x => x.loc.tempId));
    for (const loc of rows) {
      if (!drop.has(loc.tempId)) {
        result.push(loc);
      } else if (loc.id) {
        parked.push(loc);
      } else if (loc.location_name.trim()) {
        droppedUnsavedNamedCount += 1;
      }
    }
  }
  return { locations: result, parked, droppedUnsavedNamedCount, addedCount, restoredCount };
}

/** Plain-language note for the user after a sync, or '' when nothing needs saying. */
export function syncWarning(result: SyncResult): string {
  const parts: string[] = [];
  if (result.parked.length) {
    const names = result.parked.map(loc => loc.location_name.trim() || '(unnamed)').join(', ');
    parts.push(`A music line item quantity was lowered, so ${result.parked.length} saved location(s) `
      + `(${names}) will be deleted when you save. Raise the quantity again to keep them.`);
  }
  if (result.droppedUnsavedNamedCount) {
    parts.push(`${result.droppedUnsavedNamedCount} new location(s) you had named were removed because the quantity was lowered.`);
  }
  return parts.join(' ');
}

/** Did the rows change in this session compared with what the form loaded? */
export function locationsChanged(initial: ServiceLocationEntry[], current: ServiceLocationEntry[]): boolean {
  if (initial.length !== current.length) return true;
  return current.some((loc, i) => {
    const before = initial[i];
    return (
      before.tempId !== loc.tempId ||
      before.location_name !== loc.location_name ||
      before.platform !== loc.platform ||
      (before.custom_service_name || '') !== (loc.custom_service_name || '')
    );
  });
}

export interface ServiceLocationPayload {
  service_locations?: Array<{
    id?: string;
    location_name: string;
    platform: LocationPlatform;
    sort_order: number;
    custom_service_name?: string;
  }>;
  replace_service_locations?: boolean;
  remove_service_location_ids?: string[];
}

/**
 * The service-location part of a contract save.
 *  - create: the rows entered;
 *  - edit, rows unchanged: nothing (the saved rows are left exactly as they are);
 *  - edit, rows changed: the complete list (saved rows by id) as a replacement, with every saved row
 *    that is no longer in the list named in remove_service_location_ids.
 */
export function buildServiceLocationPayload(
  mode: 'create' | 'edit',
  initial: ServiceLocationEntry[],
  current: ServiceLocationEntry[],
): ServiceLocationPayload {
  const rows = current
    .filter(loc => loc.id || loc.location_name.trim())
    .map((loc, index) => ({
      ...(loc.id ? { id: loc.id } : {}),
      location_name: loc.location_name.trim(),
      platform: loc.platform,
      sort_order: index,
      ...(loc.platform === 'custom' && loc.custom_service_name ? { custom_service_name: loc.custom_service_name } : {}),
    }));
  if (mode === 'create') {
    return { service_locations: rows };
  }
  if (!locationsChanged(initial, current)) {
    return {};
  }
  const kept = new Set(current.filter(loc => loc.id).map(loc => loc.id as string));
  const removed = Array.from(new Set(
    initial.filter(loc => loc.id && !kept.has(loc.id)).map(loc => loc.id as string),
  ));
  return {
    service_locations: rows,
    replace_service_locations: true,
    remove_service_location_ids: removed,
  };
}
