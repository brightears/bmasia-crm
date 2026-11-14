/**
 * Service-location rows in the contract form.
 *
 * A contract's service-location rows (one per zone) drive its zone count and the PDF zone table.
 * The form derives *new* rows from music line items, but saved rows must never disappear as a side
 * effect of opening and saving a contract:
 *  - on load the saved rows are shown as they are (no re-derivation from line items);
 *  - a line-item change only trims rows of a product group that line items actually back
 *    (rows imported or back-filled without line items are left alone);
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

export interface SyncResult {
  locations: ServiceLocationEntry[];
  /** Saved rows (with an id) dropped by this sync; they are removed only when the form is saved. */
  droppedSavedCount: number;
  droppedNamedCount: number;
}

/**
 * Re-derive rows after a line-item change.
 *
 * @param lineBacked keys of groups that line items back now or backed earlier in this session
 *                   (a group whose line item was deleted is trimmed to zero; a group never backed by
 *                   a line item keeps all its rows).
 */
export function syncLocationsFromLineItems(
  lineItems: LineItemLike[],
  current: ServiceLocationEntry[],
  lookup: PlatformLookup,
  lineBacked: Set<string>,
  newTempId: () => string,
): SyncResult {
  const required = requiredGroups(lineItems, lookup);
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
  for (const key of Array.from(required.keys())) {
    if (!byGroup.has(key)) {
      byGroup.set(key, []);
      order.push(key);
    }
  }

  const result: ServiceLocationEntry[] = [];
  let droppedSavedCount = 0;
  let droppedNamedCount = 0;
  for (const key of order) {
    const rows = byGroup.get(key)!;
    const group = required.get(key);
    if (!group && !lineBacked.has(key)) {
      result.push(...rows); // never derived from line items: leave untouched
      continue;
    }
    const want = group ? group.required : 0;
    if (rows.length <= want) {
      result.push(...rows);
      const sample = group!;
      for (let i = rows.length; i < want; i++) {
        result.push({
          location_name: '', platform: sample.platform, tempId: newTempId(),
          ...(sample.platform === 'custom' ? { custom_service_name: sample.custom_service_name } : {}),
        });
      }
      continue;
    }
    // Too many rows: drop unnamed unsaved rows first, then unnamed saved, named unsaved, named saved.
    const rank = (loc: ServiceLocationEntry) =>
      (loc.location_name.trim() ? 2 : 0) + (loc.id ? 1 : 0);
    const dropOrder = rows
      .map((loc, index) => ({ loc, index }))
      .sort((a, b) => rank(a.loc) - rank(b.loc) || b.index - a.index);
    const drop = new Set(dropOrder.slice(0, rows.length - want).map(x => x.loc.tempId));
    for (const loc of rows) {
      if (drop.has(loc.tempId)) {
        if (loc.id) droppedSavedCount += 1;
        if (loc.location_name.trim()) droppedNamedCount += 1;
      } else {
        result.push(loc);
      }
    }
  }
  return { locations: result, droppedSavedCount, droppedNamedCount };
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
