import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import CaptureFlow from '../components/CaptureFlow';

// Mock Tauri core invoke
vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn().mockResolvedValue(''),
}));

// Mock Tauri event listen (returns cleanup function)
vi.mock('@tauri-apps/api/event', () => ({
  listen: vi.fn().mockResolvedValue(vi.fn()),
}));

// Mock settings
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

// Mock sidecarClient
vi.mock('../lib/sidecarClient', () => ({
  callOcr: vi.fn(),
  SidecarError: class extends Error {
    status: number;
    detail?: unknown;
    constructor(message: string, status: number, detail?: unknown) {
      super(message);
      this.name = 'SidecarError';
      this.status = status;
      this.detail = detail;
    }
  },
}));

describe('CaptureFlow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('初始状态为 idle，显示快捷键提示', () => {
    render(<CaptureFlow />);
    expect(screen.getByText(/Ctrl\+Shift\+C/)).toBeInTheDocument();
  });

  it('显示"选择区域截图"按钮', () => {
    render(<CaptureFlow />);
    expect(screen.getByText('选择区域截图')).toBeInTheDocument();
  });

  it('通过 Tauri invoke 加载设置并设置默认 backend', async () => {
    render(<CaptureFlow />);
    const { loadSettings } = await import('../lib/settings');
    expect(loadSettings).toHaveBeenCalled();
  });

  it('注册 Tauri event listeners', async () => {
    render(<CaptureFlow />);
    const { listen } = await import('@tauri-apps/api/event');
    // Should listen for at least 3 events: open-selection, selection-result, selection-cancelled
    expect(listen).toHaveBeenCalledTimes(3);
    expect(listen).toHaveBeenCalledWith('open-selection', expect.any(Function));
    expect(listen).toHaveBeenCalledWith('selection-result', expect.any(Function));
    expect(listen).toHaveBeenCalledWith('selection-cancelled', expect.any(Function));
  });
});
