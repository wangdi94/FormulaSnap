import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AboutSection } from '../components/settings/AboutSection';

vi.mock('../lib/i18n', () => ({
  t: (key: string) => key,
}));

describe('AboutSection', () => {
  it('渲染应用名称 FormulaSnap', () => {
    render(<AboutSection />);
    expect(screen.getByText('FormulaSnap')).toBeInTheDocument();
  });

  it('渲染版本号 v0.1.0', () => {
    render(<AboutSection />);
    expect(screen.getByText('v0.1.0')).toBeInTheDocument();
  });

  it('渲染许可证 MIT', () => {
    render(<AboutSection />);
    expect(screen.getByText('MIT')).toBeInTheDocument();
  });

  it('渲染 Section 标题和描述', () => {
    render(<AboutSection />);
    expect(screen.getByText('settings.about')).toBeInTheDocument();
    expect(screen.getByText('settings.about_description')).toBeInTheDocument();
  });
});
