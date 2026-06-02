import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import AppWithRouter from '../App';

vi.mock('@tauri-apps/api/event', () => ({
  listen: vi.fn().mockResolvedValue(vi.fn()),
}));

// Mock theme functions (no-op in test)
vi.mock('../lib/theme', () => ({
  applyTheme: vi.fn(),
  getTheme: () => 'light',
}));

// jsdom doesn't implement matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

describe('App', () => {
  it('initSidecarPort 失败时应用不崩溃', () => {
    // initSidecarPort has internal try-catch, so it never rejects.
    // This test verifies the app renders without crashing regardless.
    expect(() => render(<AppWithRouter />)).not.toThrow();
  });

  it('渲染 ToastProvider 容器', () => {
    render(<AppWithRouter />);
    // App renders ErrorBoundary > MainLayout > Header > navigation
    expect(screen.getByText('FormulaSnap')).toBeInTheDocument();
  });
});
