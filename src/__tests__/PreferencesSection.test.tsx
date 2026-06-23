import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PreferencesSection } from '../components/settings/PreferencesSection';
import type { AppSettings } from '../types/settings';

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
}));

vi.mock('../lib/constants', () => ({
  getBackendOptions: () => [
    { value: 'auto', label: 'Auto' },
    { value: 'pix2text', label: 'Pix2Text' },
    { value: 'openai', label: 'OpenAI' },
  ],
}));

function makeSettings(overrides: Partial<AppSettings> = {}): AppSettings {
  return {
    hotkey: 'Ctrl+Shift+C',
    default_backend: 'auto',
    api_keys: {},
    theme: 'system',
    monthly_budget_usd: 10,
    language: 'zh',
    ...overrides,
  };
}

describe('PreferencesSection', () => {
  const defaultProps = {
    settings: makeSettings(),
    setSettings: vi.fn(),
    recording: false,
    setRecording: vi.fn(),
    handleRecordHotkey: vi.fn(),
    hotkeyRef: { current: null } as React.RefObject<HTMLDivElement | null>,
    stats: null,
  };

  it('渲染后端选择下拉框', () => {
    render(<PreferencesSection {...defaultProps} />);
    const select = screen.getByLabelText(/settings.default_backend/) as HTMLSelectElement;
    expect(select).toBeInTheDocument();
    expect(select.value).toBe('auto');
  });

  it('渲染快捷键显示区域', () => {
    render(<PreferencesSection {...defaultProps} />);
    expect(screen.getByText('Ctrl+Shift+C')).toBeInTheDocument();
  });

  it('录制模式下显示提示文字', () => {
    render(<PreferencesSection {...defaultProps} recording={true} />);
    expect(screen.getByText('settings.press_hotkey')).toBeInTheDocument();
  });

  it('渲染预算滑块', () => {
    render(<PreferencesSection {...defaultProps} />);
    const slider = screen.getByLabelText(/settings.budget_limit/) as HTMLInputElement;
    expect(slider).toBeInTheDocument();
    expect(slider.value).toBe('10');
  });

  it('显示当前预算金额', () => {
    render(<PreferencesSection {...defaultProps} />);
    expect(screen.getByText('$10.00')).toBeInTheDocument();
  });

  it('渲染录制和重置按钮', () => {
    render(<PreferencesSection {...defaultProps} />);
    expect(screen.getByText('settings.record')).toBeInTheDocument();
    expect(screen.getByText('settings.reset')).toBeInTheDocument();
  });
});
