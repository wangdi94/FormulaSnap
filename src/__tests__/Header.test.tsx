import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Header from '../components/Header';

function renderHeader(initialPath = '/') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Header />
    </MemoryRouter>,
  );
}

describe('Header', () => {
  it('渲染应用标题', () => {
    renderHeader();
    expect(screen.getByText('FormulaSnap')).toBeInTheDocument();
  });

  it('渲染三个导航链接', () => {
    renderHeader();
    expect(screen.getByText('截图')).toBeInTheDocument();
    expect(screen.getByText('历史记录')).toBeInTheDocument();
    expect(screen.getByText('设置')).toBeInTheDocument();
  });

  it('当前路径的导航链接带有 active 样式', () => {
    renderHeader('/');
    // The "截图" link (path /) should be active
    const activeLink = screen.getByText('截图').closest('a');
    expect(activeLink?.className).toContain('bg-blue-100');
  });

  it('非当前路径的导航链接不带 active 样式', () => {
    renderHeader('/history');
    const historyLink = screen.getByText('历史记录').closest('a');
    expect(historyLink?.className).toContain('bg-blue-100');
    const homeLink = screen.getByText('截图').closest('a');
    expect(homeLink?.className).not.toContain('bg-blue-100');
  });
});
