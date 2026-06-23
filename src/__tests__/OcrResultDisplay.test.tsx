import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import OcrResultDisplay from '../components/capture/OcrResultDisplay';
import type { OcrResponse } from '../types/ocr';

vi.mock('../lib/i18n', () => ({
  t: (key: string) => key,
}));

vi.mock('../lib/constants', () => ({
  getBackendLabel: (backend: string) => `label:${backend}`,
}));

vi.mock('../components/FormulaPreview', () => ({
  default: ({ latex, readOnly }: { latex: string; readOnly: boolean }) => (
    <div data-testid="formula-preview" data-latex={latex} data-readonly={String(readOnly)}>
      Mocked FormulaPreview: {latex}
    </div>
  ),
}));

function makeResult(overrides: Partial<OcrResponse> = {}): OcrResponse {
  return {
    latex: 'E = mc^2',
    confidence: 0.95,
    backend: 'pix2text',
    timing_ms: 1200,
    ...overrides,
  };
}

describe('OcrResultDisplay', () => {
  it('渲染 FormulaPreview 组件', () => {
    render(<OcrResultDisplay result={makeResult()} />);
    expect(screen.getByTestId('formula-preview')).toBeInTheDocument();
    expect(screen.getByText('Mocked FormulaPreview: E = mc^2')).toBeInTheDocument();
  });

  it('显示后端名称', () => {
    render(<OcrResultDisplay result={makeResult()} />);
    expect(screen.getByText('label:pix2text')).toBeInTheDocument();
  });

  it('显示高置信度百分比（绿色）', () => {
    render(<OcrResultDisplay result={makeResult({ confidence: 0.95 })} />);
    const confEl = screen.getByText('95.0%');
    expect(confEl).toBeInTheDocument();
    expect(confEl.className).toContain('text-green');
  });

  it('显示中置信度百分比（黄色）', () => {
    render(<OcrResultDisplay result={makeResult({ confidence: 0.6 })} />);
    const confEl = screen.getByText('60.0%');
    expect(confEl).toBeInTheDocument();
    expect(confEl.className).toContain('text-yellow');
  });

  it('显示低置信度百分比（红色）', () => {
    render(<OcrResultDisplay result={makeResult({ confidence: 0.3 })} />);
    const confEl = screen.getByText('30.0%');
    expect(confEl).toBeInTheDocument();
    expect(confEl.className).toContain('text-red');
  });

  it('显示耗时', () => {
    render(<OcrResultDisplay result={makeResult({ timing_ms: 1200 })} />);
    expect(screen.getByText('1200 ms')).toBeInTheDocument();
  });

  it('有成本估算时显示费用', () => {
    render(
      <OcrResultDisplay
        result={makeResult({
          cost_estimate: { estimated_cost_usd: 0.0012, tokens_used: 150 },
        })}
      />,
    );
    expect(screen.getByText('$0.0012')).toBeInTheDocument();
    expect(screen.getByText('(150 tokens)')).toBeInTheDocument();
  });

  it('无成本估算时不显示费用', () => {
    render(<OcrResultDisplay result={makeResult({ cost_estimate: undefined })} />);
    expect(screen.queryByText(/\$/)).not.toBeInTheDocument();
  });
});
