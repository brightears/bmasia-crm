import {
  ServiceLocationEntry,
  buildServiceLocationPayload,
  locationsChanged,
  requiredGroups,
  syncLocationsFromLineItems,
  syncWarning,
} from './serviceLocations';

const lookup = (product: string) =>
  product === 'Soundtrack Your Brand' ? 'soundtrack' : product === 'Beat Breeze' ? 'beatbreeze' : null;

let n = 0;
const tempId = () => `t${(n += 1)}`;

const saved = (id: string, name: string, platform: ServiceLocationEntry['platform'] = 'soundtrack',
  custom = ''): ServiceLocationEntry => ({ id, location_name: name, platform, custom_service_name: custom, tempId: `s-${id}` });

describe('buildServiceLocationPayload', () => {
  test('an edit that does not touch the rows sends nothing about them', () => {
    const rows = [saved('a', 'Lobby'), saved('b', 'Pool')];
    expect(buildServiceLocationPayload('edit', rows, rows)).toEqual({});
  });

  test('an edit of a contract without rows sends nothing', () => {
    expect(buildServiceLocationPayload('edit', [], [])).toEqual({});
  });

  test('a renamed row is sent by id as a full list with no removals', () => {
    const initial = [saved('a', 'Lobby'), saved('b', 'Pool')];
    const current = [{ ...initial[0], location_name: 'Front desk' }, initial[1]];
    expect(buildServiceLocationPayload('edit', initial, current)).toEqual({
      service_locations: [
        { id: 'a', location_name: 'Front desk', platform: 'soundtrack', sort_order: 0 },
        { id: 'b', location_name: 'Pool', platform: 'soundtrack', sort_order: 1 },
      ],
      replace_service_locations: true,
      remove_service_location_ids: [],
    });
  });

  test('a saved row dropped by a quantity decrease is named for removal', () => {
    const initial = [saved('a', 'Lobby'), saved('b', 'Pool')];
    const payload = buildServiceLocationPayload('edit', initial, [initial[0]]);
    expect(payload.remove_service_location_ids).toEqual(['b']);
    expect(payload.service_locations).toEqual([{ id: 'a', location_name: 'Lobby', platform: 'soundtrack', sort_order: 0 }]);
  });

  test('create sends the entered rows without replacement or removals', () => {
    const current = [{ location_name: 'Lobby', platform: 'beatbreeze' as const, tempId: 'x' }];
    expect(buildServiceLocationPayload('create', [], current)).toEqual({
      service_locations: [{ location_name: 'Lobby', platform: 'beatbreeze', sort_order: 0 }],
    });
  });

  test('custom rows keep their product name', () => {
    const initial = [saved('a', 'Lobby', 'custom', 'Beat Breeze')];
    const current = [{ ...initial[0], location_name: 'Lobby 1' }];
    expect(buildServiceLocationPayload('edit', initial, current).service_locations).toEqual([
      { id: 'a', location_name: 'Lobby 1', platform: 'custom', sort_order: 0, custom_service_name: 'Beat Breeze' },
    ]);
  });
});

describe('syncLocationsFromLineItems', () => {
  const SYB = 'Soundtrack Your Brand';
  const counts = (entries: Array<[string, number]>) => new Map(entries);
  // A back-filled contract: 3 saved Soundtrack rows, its one Soundtrack line item says quantity 1.
  const backfilled = () => [saved('a', 'Lobby'), saved('b', 'Pool'), saved('c', 'Spa')];

  test('review scenario A: raising the quantity from 1 to 2 keeps all 3 saved rows', () => {
    const initial = backfilled();
    const r = syncLocationsFromLineItems([{ product_service: SYB, quantity: 2 }], initial, lookup,
      counts([['soundtrack', 1]]), tempId);
    expect(r.locations).toEqual(initial);
    expect(r.parked).toEqual([]);
    expect(r.addedCount).toBe(0);
    expect(buildServiceLocationPayload('edit', initial, r.locations)).toEqual({});
    expect(syncWarning(r)).toBe('');
  });

  test('review scenario B: adding a Beat Breeze line item leaves the Soundtrack rows alone', () => {
    const initial = backfilled();
    const r = syncLocationsFromLineItems(
      [{ product_service: SYB, quantity: 1 }, { product_service: 'Beat Breeze', quantity: 1 }],
      initial, lookup, counts([['soundtrack', 1]]), tempId);
    expect(r.locations.slice(0, 3)).toEqual(initial);
    expect(r.locations.slice(3).map(l => [l.platform, l.location_name])).toEqual([['beatbreeze', '']]);
    expect(r.parked).toEqual([]);
    expect(buildServiceLocationPayload('edit', initial, r.locations).remove_service_location_ids).toEqual([]);
  });

  test('lowering a quantity trims only by the decrease and names the saved row in the warning', () => {
    const initial = backfilled(); // backed by quantity 3
    const r = syncLocationsFromLineItems([{ product_service: SYB, quantity: 2 }], initial, lookup,
      counts([['soundtrack', 3]]), tempId);
    expect(r.locations.map(l => l.id)).toEqual(['a', 'b']);
    expect(r.parked.map(l => l.id)).toEqual(['c']);
    expect(syncWarning(r)).toBe('A music line item quantity was lowered, so 1 saved location(s) (Spa) '
      + 'will be deleted when you save. Raise the quantity again to keep them.');
    expect(buildServiceLocationPayload('edit', initial, r.locations).remove_service_location_ids).toEqual(['c']);
  });

  test('a decrease on a group with more saved rows than its quantity never goes below the new count', () => {
    const initial = backfilled(); // quantity 1, 3 rows
    const r = syncLocationsFromLineItems([{ product_service: SYB, quantity: 0 }], initial, lookup,
      counts([['soundtrack', 1]]), tempId);
    expect(r.locations.map(l => l.id)).toEqual(['a', 'b']); // decrease of 1 → one row, not all three
    expect(r.parked.map(l => l.id)).toEqual(['c']);
  });

  test('raising the quantity again puts the parked saved row back instead of a blank one', () => {
    const initial = backfilled();
    const down = syncLocationsFromLineItems([{ product_service: SYB, quantity: 2 }], initial, lookup,
      counts([['soundtrack', 3]]), tempId);
    const up = syncLocationsFromLineItems([{ product_service: SYB, quantity: 3 }], down.locations, lookup,
      counts([['soundtrack', 2]]), tempId, down.parked);
    expect(up.locations.map(l => l.id)).toEqual(['a', 'b', 'c']);
    expect(up.parked).toEqual([]);
    expect(up.restoredCount).toBe(1);
    expect(syncWarning(up)).toBe('');
    expect(buildServiceLocationPayload('edit', initial, up.locations)).toEqual({});
  });

  test('an increase on a group at its count adds blank rows up to the new count', () => {
    const rows = [saved('a', 'Lobby')];
    const r = syncLocationsFromLineItems([{ product_service: SYB, quantity: 3 }], rows, lookup,
      counts([['soundtrack', 1]]), tempId);
    expect(r.locations.map(x => [x.id, x.location_name])).toEqual([['a', 'Lobby'], [undefined, ''], [undefined, '']]);
    expect(r.addedCount).toBe(2);
  });

  test('a decrease drops unnamed and unsaved rows before saved named ones', () => {
    const rows = [saved('a', 'Lobby'), saved('b', 'Pool'), { location_name: '', platform: 'soundtrack' as const, tempId: 'new' }];
    const r = syncLocationsFromLineItems([{ product_service: SYB, quantity: 2 }], rows, lookup,
      counts([['soundtrack', 3]]), tempId);
    expect(r.locations.map(x => x.id)).toEqual(['a', 'b']);
    expect(r.parked).toEqual([]);
  });

  test('rows of a group no line item backs are never touched', () => {
    const rows = [saved('a', 'Lobby', 'custom', 'Beat Breeze'), saved('b', 'Pool')];
    const r = syncLocationsFromLineItems([{ product_service: 'Beat Breeze', quantity: 1 }], rows, lookup,
      counts([]), tempId);
    expect(r.locations.slice(0, 2)).toEqual(rows);
    expect(r.parked).toEqual([]);
  });

  test('deleting a line item trims its group by the old quantity only', () => {
    const rows = [saved('a', 'Lobby', 'beatbreeze'), saved('b', 'Pool', 'beatbreeze')];
    const r = syncLocationsFromLineItems([], rows, lookup, counts([['beatbreeze', 1]]), tempId);
    expect(r.locations.map(x => x.id)).toEqual(['a']);
    expect(r.parked.map(x => x.id)).toEqual(['b']);
  });
});

test('requiredGroups counts music and custom products like the form always did', () => {
  const groups = requiredGroups([
    { product_service: 'Soundtrack Your Brand', quantity: 2 },
    { product_service: 'Beat Breeze', quantity: 1 },
    { product_service: 'MP3 Download', quantity: 3 },
    { product_service: '', quantity: 1 },
  ], lookup);
  expect(Array.from(groups.entries()).map(([k, g]) => [k, g.required])).toEqual([
    ['soundtrack', 2], ['beatbreeze', 1], ['custom:MP3 Download', 3],
  ]);
});

test('locationsChanged detects edits, additions and removals only', () => {
  const rows = [saved('a', 'Lobby')];
  expect(locationsChanged(rows, [...rows])).toBe(false);
  expect(locationsChanged(rows, [{ ...rows[0], location_name: 'X' }])).toBe(true);
  expect(locationsChanged(rows, [])).toBe(true);
});
