import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Spinner } from '../components/Spinner';

describe('Spinner', () => {
  it('渲染默认尺寸（md）的 SVG', () => {
    render(<Spinner />);
    const svg = screen.getByRole('img');
    expect(svg).toBeInTheDocument();
    expect(svg.getAttribute('class')).toContain('h-5');
    expect(svg.getAttribute('class')).toContain('w-5');
  });

  it('渲染 sm 尺寸', () => {
    render(<Spinner size="sm" />);
    const svg = screen.getByRole('img');
    expect(svg.getAttribute('class')).toContain('h-4');
    expect(svg.getAttribute('class')).toContain('w-4');
  });

  it('渲染 lg 尺寸', () => {
    render(<Spinner size="lg" />);
    const svg = screen.getByRole('img');
    expect(svg.getAttribute('class')).toContain('h-8');
    expect(svg.getAttribute('class')).toContain('w-8');
  });

  it('使用自定义 title 作为无障碍标签', () => {
    render(<Spinner title="加载中" />);
    const svg = screen.getByRole('img');
    expect(svg).toHaveAttribute('aria-label', '加载中');
    expect(screen.getByText('加载中')).toBeInTheDocument();
  });

  it('默认 title 为 Loading...', () => {
    render(<Spinner />);
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('支持自定义 className', () => {
    render(<Spinner className="text-blue-500" />);
    const svg = screen.getByRole('img');
    expect(svg.getAttribute('class')).toContain('text-blue-500');
  });

  it('包含 animate-spin 动画类', () => {
    render(<Spinner />);
    const svg = screen.getByRole('img');
    expect(svg.getAttribute('class')).toContain('animate-spin');
  });
});
