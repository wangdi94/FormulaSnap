import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import StatusBar from '../components/StatusBar';

vi.mock('../lib/i18n', () => ({
  t: (key: string) => key,
}));

// Mock the settings module which uses Tauri invoke
vi.mock('../lib/settings', () => ({
  loadSettings: vi.fn().mockResolvedValue({
    hotkey: 'Ctrl+Shift+C',
    default_backend: 'pix2text',
    api_keys: {},
    theme: 'system',
    monthly_budget_usd: 10,
    language: 'zh',
  }),
}));

describe('StatusBar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('渲染就绪状态指示器', async () => {
    render(<StatusBar />);
    // Status indicator dot + "就绪" text
    expect(await screen.findByText('status.ready')).toBeInTheDocument();
  });

  it('渲染后端标签（默认 pix2text）', async () => {
    render(<StatusBar />);
    // Pix2Text (本地) is the label for pix2text backend
    expect(await screen.findByText('backend.pix2text')).toBeInTheDocument();
  });

  it('后端标签动态变化（当设置中 default_backend 改变时）', async () => {
    // Re-mock with different backend
    vi.mocked((await import('../lib/settings')).loadSettings).mockResolvedValueOnce({
      hotkey: 'Ctrl+Shift+C',
      default_backend: 'openai',
      api_keys: {},
      theme: 'system',
      monthly_budget_usd: 10,
      language: 'zh',
    });

    render(<StatusBar />);
    expect(await screen.findByText('backend.openai')).toBeInTheDocument();
  });

  it('渲染 footer 元素', async () => {
    const { container } = render(<StatusBar />);
    const footer = container.querySelector('footer');
    expect(footer).toBeInTheDocument();
  });
});
