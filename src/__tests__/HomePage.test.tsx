import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import HomePage from '../pages/HomePage';

// Mock CaptureFlow since it's complex—HomePage should render it
vi.mock('../components/CaptureFlow', () => ({
  default: () => <div data-testid="capture-flow">Mocked CaptureFlow</div>,
}));

describe('HomePage', () => {
  it('渲染标题', () => {
    render(<HomePage />);
    expect(screen.getByText('截图识别')).toBeInTheDocument();
  });

  it('渲染描述文本', () => {
    render(<HomePage />);
    expect(screen.getByText(/按下快捷键截取屏幕区域/)).toBeInTheDocument();
  });

  it('渲染 CaptureFlow 组件', () => {
    render(<HomePage />);
    expect(screen.getByTestId('capture-flow')).toBeInTheDocument();
  });
});
