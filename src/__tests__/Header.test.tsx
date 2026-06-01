import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Header from '../components/Header';

vi.mock('../lib/i18n', () => ({
  t: (key: string) => key,
}));

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
    expect(screen.getByText('nav.capture')).toBeInTheDocument();
    expect(screen.getByText('nav.history')).toBeInTheDocument();
    expect(screen.getByText('nav.settings')).toBeInTheDocument();
  });

  it('当前路径的导航链接带有 active 样式', () => {
    renderHeader('/');
    // The nav.capture link (path /) should be active
    const activeLink = screen.getByText('nav.capture').closest('a');
    expect(activeLink?.className).toContain('bg-blue-100');
  });

  it('非当前路径的导航链接不带 active 样式', () => {
    renderHeader('/history');
    const historyLink = screen.getByText('nav.history').closest('a');
    expect(historyLink?.className).toContain('bg-blue-100');
    const homeLink = screen.getByText('nav.capture').closest('a');
    expect(homeLink?.className).not.toContain('bg-blue-100');
  });
});
