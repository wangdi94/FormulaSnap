import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import FormulaPreview from '../components/FormulaPreview';

vi.mock('../lib/i18n', () => ({
  t: (key: string) => key,
}));

describe('FormulaPreview', () => {
  it('test_formula_preview_initial_value — 首次渲染显示公式', () => {
    const latex = 'E = mc^2';
    render(<FormulaPreview latex={latex} />);
    const mathField = document.querySelector('math-field');
    expect(mathField).toBeInTheDocument();
    expect(mathField).toHaveAttribute('value', latex);
  });
});
