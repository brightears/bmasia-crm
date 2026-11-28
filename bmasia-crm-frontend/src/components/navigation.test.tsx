import { buildNavGroups, filterNavForRole } from './navigation';

const paths = (role?: string) =>
  filterNavForRole(buildNavGroups(0), role).flatMap((g) => g.items.map((i) => i.path));

describe('menu by role (from the role table)', () => {
  const all = paths('Admin');

  it('shows everything to Admin and only Today to an account with no role', () => {
    expect(all.length).toBe(32);
    expect(all).toEqual(buildNavGroups(0).flatMap((g) => g.items.map((i) => i.path)));
    expect(paths(undefined)).toEqual(['/today']);
    expect(paths('')).toEqual(['/today']);
    expect(paths('Someone new')).toEqual(['/today']);
  });

  it('hides finance reports and admin pages from Sales but keeps Invoices and Contract templates', () => {
    const sales = paths('Sales');
    expect(sales).toContain('/invoices');
    expect(sales).toContain('/opportunities');
    expect(sales).toContain('/email-templates');
    expect(sales).toContain('/contract-templates');
    expect(sales).toContain('/renewals');
    expect(sales).toContain('/win-back');
    expect(sales).not.toContain('/finance/pl');
    expect(sales).not.toContain('/revenue');
    expect(sales).not.toContain('/users');
    expect(sales).not.toContain('/settings');
    expect(sales).not.toContain('/email-automations');
  });

  it('gives Finance all finance pages and no marketing or support', () => {
    const finance = paths('Finance');
    expect(finance).toContain('/finance/balance-sheet');
    expect(finance).toContain('/contracts');
    expect(finance).not.toContain('/campaigns');
    expect(finance).not.toContain('/win-back');
    expect(finance).not.toContain('/tickets');
    expect(finance).not.toContain('/users');
  });

  it.each(['Tech', 'Music'])('gives %s support pages plus contracts and tasks, without sales pipeline or finance', (role) => {
    const tech = paths(role);
    expect(tech).toEqual(expect.arrayContaining(['/tickets', '/zones', '/tech-details', '/knowledge-base', '/contracts', '/tasks', '/companies']));
    expect(tech).not.toContain('/opportunities');
    expect(tech).not.toContain('/quotes');
    expect(tech).not.toContain('/invoices');
  });

  it('no longer knows the old role names', () => {
    expect(paths('Marketing')).toEqual(['/today']);
    expect(paths('Tech Support')).toEqual(['/today']);
  });
});
