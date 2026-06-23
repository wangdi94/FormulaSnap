import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import SelectionPage from '../pages/SelectionPage';

// Mock Tauri event API
const mockListen = vi.fn();
const mockEmit = vi.fn();
const mockClose = vi.fn();

vi.mock('@tauri-apps/api/event', () => ({
  listen: (...args: unknown[]) => mockListen(...args),
  emit: (...args: unknown[]) => mockEmit(...args),
}));

vi.mock('@tauri-apps/api/window', () => ({
  getCurrentWindow: () => ({ close: mockClose }),
}));

vi.mock('../components/RegionSelector', () => ({
  default: ({
    screenshotBase64,
    onSelected,
    onCancel,
  }: {
    screenshotBase64: string;
    onSelected: (rect: { x: number; y: number; width: number; height: number }) => void;
    onCancel: () => void;
  }) => (
    <div data-testid="region-selector" data-screenshot={screenshotBase64}>
      <button type="button" data-testid="select-btn" onClick={() => onSelected({ x: 10, y: 20, width: 100, height: 50 })}>
        Select
      </button>
      <button type="button" data-testid="cancel-btn" onClick={onCancel}>Cancel</button>
    </div>
  ),
}));

describe('SelectionPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: listen resolves to an unlisten function
    mockListen.mockResolvedValue(vi.fn());
  });

  it('初始状态（无截图）渲染黑色 canvas', () => {
    const { container } = render(<SelectionPage />);
    const canvas = container.querySelector('canvas');
    expect(canvas).toBeInTheDocument();
  });

  it('注册 Tauri pre-capture 事件监听', () => {
    render(<SelectionPage />);
    expect(mockListen).toHaveBeenCalledWith('pre-capture', expect.any(Function));
  });

  it('收到截图数据后渲染 RegionSelector', async () => {
    let captureHandler: (event: { payload: string }) => void;
    mockListen.mockImplementation((event: string, handler: (event: { payload: string }) => void) => {
      if (event === 'pre-capture') captureHandler = handler;
      return Promise.resolve(vi.fn());
    });

    render(<SelectionPage />);

    // Simulate receiving screenshot data
    await act(async () => {
      captureHandler!({ payload: 'fake-base64-data' });
    });

    expect(screen.getByTestId('region-selector')).toBeInTheDocument();
    expect(screen.getByTestId('region-selector')).toHaveAttribute('data-screenshot', 'fake-base64-data');
  });

  it('选择区域后 emit selection-result 并关闭窗口', async () => {
    let captureHandler: (event: { payload: string }) => void;
    mockListen.mockImplementation((event: string, handler: (event: { payload: string }) => void) => {
      if (event === 'pre-capture') captureHandler = handler;
      return Promise.resolve(vi.fn());
    });
    mockEmit.mockResolvedValue(undefined);
    mockClose.mockResolvedValue(undefined);

    render(<SelectionPage />);

    await act(async () => {
      captureHandler!({ payload: 'fake-base64-data' });
    });

    await act(async () => {
      fireEvent.click(screen.getByTestId('select-btn'));
    });

    expect(mockEmit).toHaveBeenCalledWith('selection-result', { x: 10, y: 20, width: 100, height: 50 });
    expect(mockClose).toHaveBeenCalled();
  });

  it('取消选择后 emit selection-cancelled 并关闭窗口', async () => {
    let captureHandler: (event: { payload: string }) => void;
    mockListen.mockImplementation((event: string, handler: (event: { payload: string }) => void) => {
      if (event === 'pre-capture') captureHandler = handler;
      return Promise.resolve(vi.fn());
    });
    mockEmit.mockResolvedValue(undefined);
    mockClose.mockResolvedValue(undefined);

    render(<SelectionPage />);

    await act(async () => {
      captureHandler!({ payload: 'fake-base64-data' });
    });

    await act(async () => {
      fireEvent.click(screen.getByTestId('cancel-btn'));
    });

    expect(mockEmit).toHaveBeenCalledWith('selection-cancelled');
    expect(mockClose).toHaveBeenCalled();
  });

  it('按 Escape 键触发取消', async () => {
    let captureHandler: (event: { payload: string }) => void;
    mockListen.mockImplementation((event: string, handler: (event: { payload: string }) => void) => {
      if (event === 'pre-capture') captureHandler = handler;
      return Promise.resolve(vi.fn());
    });
    mockEmit.mockResolvedValue(undefined);
    mockClose.mockResolvedValue(undefined);

    render(<SelectionPage />);

    await act(async () => {
      captureHandler!({ payload: 'fake-base64-data' });
    });

    await act(async () => {
      fireEvent.keyDown(window, { key: 'Escape' });
    });

    expect(mockEmit).toHaveBeenCalledWith('selection-cancelled');
  });
});
