import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import CaptureActions from '../components/capture/CaptureActions';

vi.mock('../lib/i18n', () => ({
  t: (key: string) => key,
}));

describe('CaptureActions', () => {
  describe('error 模式', () => {
    it('渲染重试按钮（retryable=true）', () => {
      render(
        <CaptureActions
          mode="error"
          retryable={true}
          onRetry={vi.fn()}
          onReset={vi.fn()}
        />,
      );
      expect(screen.getByText('common.retry')).toBeInTheDocument();
      expect(screen.getByText('capture.retake')).toBeInTheDocument();
    });

    it('retryable=false 时不显示重试按钮', () => {
      render(
        <CaptureActions
          mode="error"
          retryable={false}
          onRetry={vi.fn()}
          onReset={vi.fn()}
        />,
      );
      expect(screen.queryByText('common.retry')).not.toBeInTheDocument();
      expect(screen.getByText('capture.retake')).toBeInTheDocument();
    });

    it('点击重试按钮调用 onRetry', () => {
      const onRetry = vi.fn();
      render(
        <CaptureActions
          mode="error"
          retryable={true}
          onRetry={onRetry}
          onReset={vi.fn()}
        />,
      );
      fireEvent.click(screen.getByText('common.retry'));
      expect(onRetry).toHaveBeenCalledTimes(1);
    });

    it('点击重拍按钮调用 onReset', () => {
      const onReset = vi.fn();
      render(
        <CaptureActions
          mode="error"
          retryable={false}
          onRetry={vi.fn()}
          onReset={onReset}
        />,
      );
      fireEvent.click(screen.getByText('capture.retake'));
      expect(onReset).toHaveBeenCalledTimes(1);
    });
  });

  describe('result 模式', () => {
    it('渲染新截图按钮', () => {
      render(
        <CaptureActions mode="result" onReset={vi.fn()} />,
      );
      expect(screen.getByText('capture.new_screenshot')).toBeInTheDocument();
    });

    it('点击新截图按钮调用 onReset', () => {
      const onReset = vi.fn();
      render(
        <CaptureActions mode="result" onReset={onReset} />,
      );
      fireEvent.click(screen.getByText('capture.new_screenshot'));
      expect(onReset).toHaveBeenCalledTimes(1);
    });

    it('result 模式不显示重试按钮', () => {
      render(
        <CaptureActions mode="result" onReset={vi.fn()} />,
      );
      expect(screen.queryByText('common.retry')).not.toBeInTheDocument();
    });
  });
});
