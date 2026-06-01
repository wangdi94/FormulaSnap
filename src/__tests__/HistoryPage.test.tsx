import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import HistoryPage from '../pages/HistoryPage';

// Mock Tauri invoke
const mockInvoke = vi.fn();
vi.mock('@tauri-apps/api/core', () => ({
  invoke: (...args: unknown[]) => mockInvoke(...args),
}));

function renderHistoryPage() {
  return render(
    <MemoryRouter>
      <HistoryPage />
    </MemoryRouter>,
  );
}

describe('HistoryPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('渲染页面标题', () => {
    renderHistoryPage();
    expect(screen.getByText('历史记录')).toBeInTheDocument();
  });

  it('渲染搜索输入框', () => {
    renderHistoryPage();
    expect(screen.getByPlaceholderText('搜索 LaTeX 公式...')).toBeInTheDocument();
  });

  it('加载数据时显示加载状态', () => {
    // Return a promise that never settles to keep loading
    mockInvoke.mockReturnValue(new Promise(() => {}));
    renderHistoryPage();
    expect(screen.getAllByText('加载中...').length).toBeGreaterThan(0);
  });

  it('无数据时显示空状态', async () => {
    mockInvoke.mockResolvedValue([]);
    renderHistoryPage();
    expect(await screen.findByText('暂无历史记录')).toBeInTheDocument();
  });

  it('有数据时渲染历史条目', async () => {
    mockInvoke.mockResolvedValue([
      {
        id: 1,
        created_at: new Date().toISOString(),
        latex: 'x^2 + y^2 = z^2',
        backend: 'pix2text',
        confidence: 0.95,
        screenshot_path: null,
      },
    ]);
    renderHistoryPage();
    expect(await screen.findByText('x^2 + y^2 = z^2')).toBeInTheDocument();
  });

  it('调用 Tauri API 加载数据', async () => {
    mockInvoke.mockResolvedValue([]);
    renderHistoryPage();
    await screen.findByText('暂无历史记录');
    expect(mockInvoke).toHaveBeenCalledWith('get_history', {
      limit: 20,
      offset: 0,
    });
  });
});
