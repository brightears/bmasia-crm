import {
  ServiceLocationEntry,
  buildServiceLocationPayload,
  locationsChanged,
  requiredGroups,
  syncLocationsFromLineItems,
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
  test('rows never backed by a line item survive a line-item change', () => {
    const rows = [saved('a', 'Lobby', 'custom', 'Beat Breeze'), saved('b', 'Pool', 'soundtrack')];
    const lineItems = [{ product_service: 'Windows Mini PC', quantity: 0 }];
    const result = syncLocationsFromLineItems(lineItems, rows, lookup, new Set(), tempId);
    expect(result.locations).toEqual(rows);
    expect(result.droppedSavedCount).toBe(0);
  });

  test('an added music line item adds blank rows and keeps the saved ones', () => {
    const rows = [saved('a', 'Lobby')];
    const result = syncLocationsFromLineItems(
      [{ product_service: 'Soundtrack Your Brand', quantity: 3 }], rows, lookup, new Set(), tempId);
    expect(result.locations.map(r => [r.id, r.location_name])).toEqual([['a', 'Lobby'], [undefined, ''], [undefined, '']]);
  });

  test('a quantity decrease drops unsaved and unnamed rows before saved named ones', () => {
    const rows = [saved('a', 'Lobby'), saved('b', 'Pool'),
      { location_name: '', platform: 'soundtrack' as const, tempId: 'new' }];
    const result = syncLocationsFromLineItems(
      [{ product_service: 'Soundtrack Your Brand', quantity: 2 }], rows, lookup, new Set(['soundtrack']), tempId);
    expect(result.locations.map(r => r.id)).toEqual(['a', 'b']);
    expect(result.droppedSavedCount).toBe(0);
  });

  test('a deliberate decrease below the saved rows drops the last saved row and reports it', () => {
    const rows = [saved('a', 'Lobby'), saved('b', 'Pool'), saved('c', 'Spa')];
    const result = syncLocationsFromLineItems(
      [{ product_service: 'Soundtrack Your Brand', quantity: 2 }], rows, lookup, new Set(['soundtrack']), tempId);
    expect(result.locations.map(r => r.id)).toEqual(['a', 'b']);
    expect(result.droppedSavedCount).toBe(1);
  });

  test('removing the line item of a backed group drops its rows', () => {
    const rows = [saved('a', 'Lobby', 'beatbreeze')];
    const result = syncLocationsFromLineItems([], rows, lookup, new Set(['beatbreeze']), tempId);
    expect(result.locations).toEqual([]);
    expect(result.droppedSavedCount).toBe(1);
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
