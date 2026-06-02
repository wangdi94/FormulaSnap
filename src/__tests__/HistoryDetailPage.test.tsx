import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import HistoryDetailPage from '../pages/HistoryDetailPage';

// ── Mocks ──

const mockInvoke = vi.fn();
vi.mock('@tauri-apps/api/core', () => ({
  invoke: (...args: unknown[]) => mockInvoke(...args),
  convertFileSrc: (p: string) => `asset://localhost/${p}`,
}));

vi.mock('@tauri-apps/plugin-clipboard-manager', () => ({
  writeText: vi.fn().mockResolvedValue(undefined),
  writeImage: vi.fn().mockResolvedValue(undefined),
}));

vi.mock('mathlive', () => ({
  convertLatexToMarkup: vi.fn().mockReturnValue('<span>mock</span>'),
}));

vi.mock('mathlive/ssr', () => ({
  convertLatexToMathMl: vi.fn().mockReturnValue('<math>mock</math>'),
}));

vi.mock('mathlive/static.css?inline', () => ({ default: '' }));

const mockCopyToClipboard = vi.fn().mockResolvedValue(undefined);
vi.mock('../lib/clipboard', async () => {
  const actual = await vi.importActual<typeof import('../lib/clipboard')>('../lib/clipboard');
  return {
    ...actual,
    copyToClipboard: (...args: unknown[]) => mockCopyToClipboard(...args),
  };
});

vi.mock('../lib/i18n', () => ({
  t: (key: string, vars?: Record<string, unknown>) =>
    vars ? `${key}:${JSON.stringify(vars)}` : key,
  getLocale: () => 'en-US',
}));

vi.mock('../components/FormulaPreview', () => ({
  default: ({ latex }: { latex: string }) => (
    <div data-testid="formula-preview">{latex}</div>
  ),
}));

// ── Helpers ──

const FAKE_ENTRY = {
  id: 42,
  created_at: '2025-06-01T10:00:00Z',
  latex: 'E = mc^2',
  backend: 'pix2text',
  confidence: 0.95,
  screenshot_path: null,
};

function renderDetail(id = '42') {
  return render(
    <MemoryRouter initialEntries={[`/history/${id}`]}>
      <Routes>
        <Route path="/history/:id" element={<HistoryDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

// ── Tests ──

describe('HistoryDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('test_unmount_during_load — 加载中卸载不调用 setState', async () => {
    // invoke 永不 resolve，模拟加载中
    let resolveInvoke!: (v: unknown) => void;
    mockInvoke.mockReturnValue(new Promise((r) => { resolveInvoke = r; }));

    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    const { unmount } = renderDetail();

    // 确认正在加载
    expect(screen.getByRole('status')).toBeInTheDocument();

    // 卸载组件（此时 invoke 还未 resolve）
    unmount();

    // 让 invoke resolve — 此时组件已卸载，不应触发 setState
    await act(async () => {
      resolveInvoke(FAKE_ENTRY);
    });

    consoleSpy.mockRestore();
  });

  it('test_copy_state_not_stuck — 快速切换格式复制不卡住状态', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    mockInvoke.mockResolvedValue(FAKE_ENTRY);

    renderDetail();

    // 等待加载完成
    await waitFor(() => {
      expect(screen.getByTestId('formula-preview')).toHaveTextContent('E = mc^2');
    });

    // 点击 LaTeX 复制
    fireEvent.click(screen.getByText('history.copy_latex'));

    // 等待 LaTeX 复制完成
    await waitFor(() => {
      expect(screen.getByText('history.copied')).toBeInTheDocument();
    });

    // 点击 MathML 复制
    fireEvent.click(screen.getByText('history.copy_mathml'));

    // 等待 MathML 也进入 copied 状态
    await waitFor(() => {
      // MathML 也 copied 了（LaTeX 的 copied 已被 MathML 的 copied 替换为新 copied）
      expect(screen.getByText('history.copied')).toBeInTheDocument();
    });

    // 推进时间让两个 timeout 都触发
    await act(async () => {
      vi.advanceTimersByTime(3000);
    });

    // 两个按钮都应恢复到初始 label
    expect(screen.getByText('history.copy_latex')).toBeInTheDocument();
    expect(screen.getByText('history.copy_mathml')).toBeInTheDocument();

    vi.useRealTimers();
  });
});
