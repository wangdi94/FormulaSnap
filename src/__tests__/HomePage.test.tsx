import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import HomePage from '../pages/HomePage';

vi.mock('../lib/i18n', () => ({
  t: (key: string) => key,
}));

// Mock CaptureFlow since it's complex—HomePage should render it
vi.mock('../components/CaptureFlow', () => ({
  default: () => <div data-testid="capture-flow">Mocked CaptureFlow</div>,
}));

describe('HomePage', () => {
  it('渲染标题', () => {
    render(<HomePage />);
    expect(screen.getByText('home.title')).toBeInTheDocument();
  });

  it('渲染描述文本', () => {
    render(<HomePage />);
    expect(screen.getByText('home.description')).toBeInTheDocument();
  });

  it('渲染 CaptureFlow 组件', () => {
    render(<HomePage />);
    expect(screen.getByTestId('capture-flow')).toBeInTheDocument();
  });
});
