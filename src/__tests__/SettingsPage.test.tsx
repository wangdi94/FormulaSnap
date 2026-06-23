import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import SettingsPage from '../pages/SettingsPage';

// Mock i18n
vi.mock('../lib/i18n', () => ({
  t: (key: string, params?: Record<string, string>) => {
    if (params) {
      let result = key;
      for (const [k, v] of Object.entries(params)) {
        result = result.replace(`{${k}}`, v);
      }
      return result;
    }
    return key;
  },
  setLang: vi.fn(),
}));

// Mock settings module
const mockLoadSettings = vi.fn();
const mockSaveSettings = vi.fn();
const mockResetSettings = vi.fn();

vi.mock('../lib/settings', () => ({
  loadSettings: (...args: unknown[]) => mockLoadSettings(...args),
  saveSettings: (...args: unknown[]) => mockSaveSettings(...args),
  resetSettings: (...args: unknown[]) => mockResetSettings(...args),
}));

// Mock sidecarClient
const mockGetStats = vi.fn();
const mockSaveApiKey = vi.fn();
const mockGetApiKeys = vi.fn();

vi.mock('../lib/sidecarClient', () => ({
  getStats: (...args: unknown[]) => mockGetStats(...args),
  saveApiKey: (...args: unknown[]) => mockSaveApiKey(...args),
  getApiKeys: (...args: unknown[]) => mockGetApiKeys(...args),
}));

// Mock settings sub-components
vi.mock('../components/settings', () => ({
  ApiKeySection: () => <div data-testid="api-key-section">ApiKeySection</div>,
  API_KEY_FIELDS: [
    { key: 'openai', label: 'OpenAI' },
    { key: 'claude', label: 'Claude' },
  ],
  PreferencesSection: () => <div data-testid="preferences-section">PreferencesSection</div>,
  normalizeModifiers: vi.fn(() => []),
  keyToReadable: vi.fn((code: string) => code),
  StatsSection: () => <div data-testid="stats-section">StatsSection</div>,
  AboutSection: () => <div data-testid="about-section">AboutSection</div>,
}));

// Mock Spinner
vi.mock('../components/Spinner', () => ({
  Spinner: ({ title }: { title?: string }) => (
    <div data-testid="spinner" role="img">
      {title}
    </div>
  ),
}));

const DEFAULT_SETTINGS = {
  hotkey: 'Ctrl+Shift+C',
  default_backend: 'auto' as const,
  api_keys: {},
  theme: 'system' as const,
  monthly_budget_usd: 10,
  language: 'zh' as const,
};

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockLoadSettings.mockResolvedValue(DEFAULT_SETTINGS);
    mockSaveSettings.mockResolvedValue(undefined);
    mockResetSettings.mockResolvedValue(DEFAULT_SETTINGS);
    mockGetStats.mockResolvedValue({
      total_recognitions: 100,
      total_cost_usd: 1.5,
      monthly_cost_usd: 0.3,
    });
    mockSaveApiKey.mockResolvedValue(undefined);
    mockGetApiKeys.mockResolvedValue({
      keys: [
        { backend: 'openai', configured: true },
        { backend: 'claude', configured: false },
      ],
    });
  });

  it('加载中显示 Spinner', () => {
    // Make loadSettings hang so we stay in loading state
    mockLoadSettings.mockReturnValue(new Promise(() => {}));
    render(<SettingsPage />);
    expect(screen.getByText('settings.loading')).toBeInTheDocument();
    expect(screen.getByTestId('spinner')).toBeInTheDocument();
  });

  it('加载完成后渲染设置页面标题', async () => {
    render(<SettingsPage />);
    await waitFor(() => {
      expect(screen.getByText('settings.page_title')).toBeInTheDocument();
    });
    expect(screen.getByText('settings.description')).toBeInTheDocument();
  });

  it('渲染所有设置子组件', async () => {
    render(<SettingsPage />);
    await waitFor(() => {
      expect(screen.getByTestId('api-key-section')).toBeInTheDocument();
    });
    expect(screen.getByTestId('preferences-section')).toBeInTheDocument();
    expect(screen.getByTestId('stats-section')).toBeInTheDocument();
    expect(screen.getByTestId('about-section')).toBeInTheDocument();
  });

  it('渲染保存和重置按钮', async () => {
    render(<SettingsPage />);
    await waitFor(() => {
      expect(screen.getByText('settings.save_settings')).toBeInTheDocument();
    });
    expect(screen.getByText('settings.reset_default')).toBeInTheDocument();
  });

  it('点击保存按钮调用 saveSettings', async () => {
    render(<SettingsPage />);
    await waitFor(() => {
      expect(screen.getByText('settings.save_settings')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('settings.save_settings'));

    await waitFor(() => {
      expect(mockSaveSettings).toHaveBeenCalled();
    });
  });

  it('加载失败时使用默认设置', async () => {
    mockLoadSettings.mockRejectedValue(new Error('load failed'));
    render(<SettingsPage />);
    await waitFor(() => {
      expect(screen.getByText('settings.page_title')).toBeInTheDocument();
    });
  });
});
