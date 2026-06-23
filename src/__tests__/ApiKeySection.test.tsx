import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ApiKeySection, API_KEY_FIELDS } from '../components/settings/ApiKeySection';
import type { AppSettings } from '../types/settings';

vi.mock('../lib/i18n', () => ({
  t: (key: string) => key,
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

describe('ApiKeySection', () => {
  const defaultProps = {
    settings: makeSettings(),
    updateApiKey: vi.fn(),
    showKeys: {} as Record<string, boolean>,
    setShowKeys: vi.fn(),
    configuredKeys: {} as Record<string, boolean>,
  };

  it('渲染所有 API Key 输入字段', () => {
    render(<ApiKeySection {...defaultProps} />);
    for (const field of API_KEY_FIELDS) {
      expect(screen.getByLabelText(new RegExp(field.label))).toBeInTheDocument();
    }
  });

  it('输入框默认为密码类型', () => {
    render(<ApiKeySection {...defaultProps} />);
    const input = screen.getByLabelText(/OpenAI API Key/) as HTMLInputElement;
    expect(input.type).toBe('password');
  });

  it('showKeys 为 true 时输入框显示为文本类型', () => {
    render(
      <ApiKeySection
        {...defaultProps}
        showKeys={{ openai: true }}
      />,
    );
    const input = screen.getByLabelText(/OpenAI API Key/) as HTMLInputElement;
    expect(input.type).toBe('text');
  });

  it('已配置的 key 显示 "已配置" 标签', () => {
    render(
      <ApiKeySection
        {...defaultProps}
        configuredKeys={{ openai: true }}
      />,
    );
    expect(screen.getByText('settings.key_configured')).toBeInTheDocument();
  });

  it('输入值变化时调用 updateApiKey', () => {
    const updateApiKey = vi.fn();
    render(<ApiKeySection {...defaultProps} updateApiKey={updateApiKey} />);
    const input = screen.getByLabelText(/OpenAI API Key/) as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'sk-test123' } });
    expect(updateApiKey).toHaveBeenCalledWith('openai', 'sk-test123');
  });

  it('渲染 API Key 管理标题', () => {
    render(<ApiKeySection {...defaultProps} />);
    expect(screen.getByText('settings.api_key_management')).toBeInTheDocument();
  });
});
