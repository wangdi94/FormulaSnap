import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { ToastProvider, ToastContext } from '../components/Toast';
import { useContext } from 'react';
import type { ReactNode } from 'react';

// Consumer to trigger toasts through context
let triggerToast: ((type: 'success' | 'warning' | 'error', message: string) => void) | null = null;

function ToastConsumer() {
  const ctx = useContext(ToastContext);
  if (!ctx) return null;
  triggerToast = ctx.toast;
  return null;
}

function renderWithProvider(children: ReactNode) {
  return render(
    <ToastProvider>
      {children}
      <ToastConsumer />
    </ToastProvider>,
  );
}

beforeEach(() => {
  triggerToast = null;
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('ToastProvider', () => {
  it('渲染子组件', () => {
    render(<ToastProvider><div>内容</div></ToastProvider>);
    expect(screen.getByText('内容')).toBeInTheDocument();
  });

  it('通过 context 添加成功 toast', () => {
    renderWithProvider(<div />);
    act(() => {
      triggerToast?.('success', '操作成功！');
    });
    expect(screen.getByText('操作成功！')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toBeInTheDocument();
    // Should have success icon (a checkmark path)
    const svg = document.querySelector('svg');
    expect(svg).toBeInTheDocument();
  });

  it('添加 warning toast', () => {
    renderWithProvider(<div />);
    act(() => {
      triggerToast?.('warning', '注意：配置未保存');
    });
    expect(screen.getByText('注意：配置未保存')).toBeInTheDocument();
  });

  it('添加 error toast', () => {
    renderWithProvider(<div />);
    act(() => {
      triggerToast?.('error', '请求失败');
    });
    expect(screen.getByText('请求失败')).toBeInTheDocument();
  });

  it('toast 有关闭按钮可手动关闭', () => {
    renderWithProvider(<div />);
    act(() => {
      triggerToast?.('success', '可关闭');
    });
    expect(screen.getByText('可关闭')).toBeInTheDocument();

    // Click close button
    const closeButton = screen.getByLabelText('关闭');
    fireEvent.click(closeButton);
    // Toast should be removed
    expect(screen.queryByText('可关闭')).not.toBeInTheDocument();
  });

  it('toast 在 duration 后自动消失', () => {
    renderWithProvider(<div />);
    act(() => {
      triggerToast?.('success', '自动消失');
    });
    expect(screen.getByText('自动消失')).toBeInTheDocument();

    // Fast-forward past default duration (3000ms)
    act(() => {
      vi.advanceTimersByTime(3000);
    });
    expect(screen.queryByText('自动消失')).not.toBeInTheDocument();
  });

  it('支持多个同时显示的 toast', () => {
    renderWithProvider(<div />);
    act(() => {
      triggerToast?.('success', '成功通知');
      triggerToast?.('warning', '警告通知');
    });
    expect(screen.getByText('成功通知')).toBeInTheDocument();
    expect(screen.getByText('警告通知')).toBeInTheDocument();
    // Should have 2 alerts
    expect(screen.getAllByRole('alert')).toHaveLength(2);
  });
});
