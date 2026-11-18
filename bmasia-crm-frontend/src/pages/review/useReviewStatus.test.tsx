import React from 'react';
import { act, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import reviewApi from '../../services/reviewApi';
import { buildNavGroups, filterNavForRole } from '../../components/navigation';
import { resetReviewSettingsCache, useReviewNavStatus } from './useReviewStatus';
import CompanyReviewLink from './CompanyReviewLink';
import { settingsOn } from './testFixtures';

jest.mock('../../services/authService', () => ({ __esModule: true, default: {}, authApi: {} }));
jest.mock('../../services/reviewApi', () => {
  const actual = jest.requireActual('../../services/reviewApi');
  return { __esModule: true, ...actual, default: { getSettings: jest.fn(), openCount: jest.fn() } };
});

const api = reviewApi as jest.Mocked<typeof reviewApi>;
const off = { ...settingsOn, proposals_enabled: false };

/** The menu exactly as Layout builds it: buildNavGroups with the hook's object, then the role filter. */
const Menu: React.FC = () => {
  const review = useReviewNavStatus();
  const paths = filterNavForRole(buildNavGroups(0, review), 'Admin').flatMap((g) =>
    g.items.map((i) => `${i.path}${i.badge ? `:${i.badge}` : ''}`),
  );
  return <div data-testid="menu">{paths.join(' ')}</div>;
};

const setVisibility = (state: 'visible' | 'hidden') => {
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => state });
  document.dispatchEvent(new Event('visibilitychange'));
};

beforeEach(() => {
  jest.resetAllMocks();
  resetReviewSettingsCache();
  setVisibility('visible');
});

afterEach(() => {
  jest.useRealTimers();
});

describe('switched off', () => {
  it('has no Review entry when Layout passes {enabled: false}', () => {
    const paths = buildNavGroups(5, { enabled: false, openCount: 5 }).flatMap((g) => g.items.map((i) => i.path));
    expect(paths).not.toContain('/review');
  });

  it('reads the switch once and never polls or lists while off', async () => {
    jest.useFakeTimers();
    api.getSettings.mockResolvedValue(off);
    render(<Menu />);
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByTestId('menu').textContent).not.toContain('/review');
    await act(async () => {
      jest.advanceTimersByTime(10 * 60_000);
    });
    expect(api.getSettings).toHaveBeenCalledTimes(1);
    expect(api.openCount).not.toHaveBeenCalled();
  });

  it('reads the switch again when the tab becomes visible, at most once a minute', async () => {
    jest.useFakeTimers();
    api.getSettings.mockResolvedValue(off);
    render(<Menu />);
    await act(async () => {
      await Promise.resolve();
    });
    await act(async () => {
      setVisibility('visible');
      await Promise.resolve();
    });
    expect(api.getSettings).toHaveBeenCalledTimes(1);
    await act(async () => {
      jest.advanceTimersByTime(61_000);
    });
    await act(async () => {
      setVisibility('visible');
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(api.getSettings).toHaveBeenCalledTimes(2);
  });

  it('counts a failed read as off, without an entry or a list call', async () => {
    api.getSettings.mockRejectedValue(new Error('down'));
    render(<Menu />);
    await waitFor(() => expect(api.getSettings).toHaveBeenCalled());
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByTestId('menu').textContent).not.toContain('/review');
    expect(api.openCount).not.toHaveBeenCalled();
  });

  it('shows no company chip and makes no list call', async () => {
    api.getSettings.mockResolvedValue(off);
    render(
      <MemoryRouter>
        <CompanyReviewLink companyId="c-1" />
      </MemoryRouter>,
    );
    await waitFor(() => expect(api.getSettings).toHaveBeenCalled());
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.queryByTestId('company-review-link')).not.toBeInTheDocument();
    expect(api.openCount).not.toHaveBeenCalled();
  });
});

describe('switched on', () => {
  it('shows the entry with the count and polls only while the tab is visible', async () => {
    jest.useFakeTimers();
    api.getSettings.mockResolvedValue(settingsOn);
    api.openCount.mockResolvedValue(7);
    render(<Menu />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByTestId('menu').textContent).toContain('/review:7');
    expect(api.openCount).toHaveBeenCalledTimes(1);
    await act(async () => {
      jest.advanceTimersByTime(60_000);
    });
    expect(api.openCount).toHaveBeenCalledTimes(2);
    act(() => setVisibility('hidden'));
    await act(async () => {
      jest.advanceTimersByTime(5 * 60_000);
    });
    expect(api.openCount).toHaveBeenCalledTimes(2);
  });
});
