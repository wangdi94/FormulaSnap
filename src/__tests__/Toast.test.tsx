import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { ToastProvider, ToastContext } from '../components/Toast';
import { useContext, useEffect } from 'react';
import type { ReactNode } from 'react';

vi.mock('../lib/i18n', () => ({
  t: (key: string) => key,
}));

// Consumer to trigger toasts through context
let triggerToast: ((type: 'success' | 'warning' | 'error', message: string) => void) | null = null;

function ToastConsumer() {
  const ctx = useContext(ToastContext);
  useEffect(() => {
    triggerToast = ctx?.toast ?? null;
    return () => { triggerToast = null; };
  }, [ctx?.toast]);
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
      triggerToast?.('success', 'Operation successful!');
    });
    expect(screen.getByText('Operation successful!')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toBeInTheDocument();
    // Should have success icon (a checkmark path)
    const svg = document.querySelector('svg');
    expect(svg).toBeInTheDocument();
  });

  it('添加 warning toast', () => {
    renderWithProvider(<div />);
    act(() => {
      triggerToast?.('warning', 'Warning: config not saved');
    });
    expect(screen.getByText('Warning: config not saved')).toBeInTheDocument();
  });

  it('添加 error toast', () => {
    renderWithProvider(<div />);
    act(() => {
      triggerToast?.('error', 'Request failed');
    });
    expect(screen.getByText('Request failed')).toBeInTheDocument();
  });

  it('toast 有关闭按钮可手动关闭', () => {
    renderWithProvider(<div />);
    act(() => {
      triggerToast?.('success', 'Dismissible');
    });
    expect(screen.getByText('Dismissible')).toBeInTheDocument();

    // Click close button
    const closeButton = screen.getByLabelText('common.close');
    fireEvent.click(closeButton);
    // Toast should be removed
    expect(screen.queryByText('Dismissible')).not.toBeInTheDocument();
  });

  it('toast 在 duration 后自动消失', () => {
    renderWithProvider(<div />);
    act(() => {
      triggerToast?.('success', 'Auto dismiss');
    });
    expect(screen.getByText('Auto dismiss')).toBeInTheDocument();

    // Fast-forward past default duration (3000ms)
    act(() => {
      vi.advanceTimersByTime(3000);
    });
    expect(screen.queryByText('Auto dismiss')).not.toBeInTheDocument();
  });

  it('支持多个同时显示的 toast', () => {
    renderWithProvider(<div />);
    act(() => {
      triggerToast?.('success', 'Success notification');
      triggerToast?.('warning', 'Warning notification');
    });
    expect(screen.getByText('Success notification')).toBeInTheDocument();
    expect(screen.getByText('Warning notification')).toBeInTheDocument();
    // Should have 2 alerts
    expect(screen.getAllByRole('alert')).toHaveLength(2);
  });
});
