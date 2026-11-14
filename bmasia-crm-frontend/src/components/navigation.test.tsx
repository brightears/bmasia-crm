import { buildNavGroups, filterNavForRole } from './navigation';

const paths = (role?: string) =>
  filterNavForRole(buildNavGroups(0), role).flatMap((g) => g.items.map((i) => i.path));

describe('menu by role (display only)', () => {
  const all = paths('Admin');

  it('shows everything to Admin and to unknown or missing roles', () => {
    expect(all.length).toBe(30);
    expect(paths(undefined)).toEqual(all);
    expect(paths('Someone new')).toEqual(all);
  });

  it('hides finance reports and admin pages from Sales but keeps Invoices', () => {
    const sales = paths('Sales');
    expect(sales).toContain('/invoices');
    expect(sales).toContain('/opportunities');
    expect(sales).not.toContain('/finance/pl');
    expect(sales).not.toContain('/revenue');
    expect(sales).not.toContain('/users');
  });

  it('gives Finance all finance pages and no marketing or support', () => {
    const finance = paths('Finance');
    expect(finance).toContain('/finance/balance-sheet');
    expect(finance).toContain('/contracts');
    expect(finance).not.toContain('/campaigns');
    expect(finance).not.toContain('/tickets');
  });

  it('gives Tech support pages plus contracts and tasks, without sales pipeline or finance', () => {
    const tech = paths('Tech');
    expect(tech).toEqual(expect.arrayContaining(['/tickets', '/zones', '/tech-details', '/contracts', '/tasks', '/companies']));
    expect(tech).not.toContain('/opportunities');
    expect(tech).not.toContain('/invoices');
  });
});
