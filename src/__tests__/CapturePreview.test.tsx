import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import CapturePreview from '../components/capture/CapturePreview';

vi.mock('../lib/i18n', () => ({
  t: (key: string) => key,
}));

const FAKE_BASE64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';

describe('CapturePreview', () => {
  describe('loading 变体', () => {
    it('渲染半透明缩略图', () => {
      render(<CapturePreview imageBase64={FAKE_BASE64} variant="loading" />);
      const img = screen.getByRole('img');
      expect(img).toBeInTheDocument();
      expect(img).toHaveAttribute('src', `data:image/png;base64,${FAKE_BASE64}`);
      expect(img.className).toContain('opacity-60');
    });

    it('使用正确的 alt 文本', () => {
      render(<CapturePreview imageBase64={FAKE_BASE64} variant="loading" />);
      expect(screen.getByAltText('capture.screenshot_preview')).toBeInTheDocument();
    });
  });

  describe('result 变体', () => {
    it('渲染可折叠的详情组件', () => {
      const { container } = render(
        <CapturePreview imageBase64={FAKE_BASE64} variant="result" />,
      );
      const details = container.querySelector('details');
      expect(details).toBeInTheDocument();
    });

    it('显示截图预览摘要文本', () => {
      render(<CapturePreview imageBase64={FAKE_BASE64} variant="result" />);
      expect(screen.getByText('capture.screenshot_preview')).toBeInTheDocument();
    });

    it('包含截图图片', () => {
      render(<CapturePreview imageBase64={FAKE_BASE64} variant="result" />);
      expect(screen.getByAltText('capture.screenshot')).toBeInTheDocument();
    });
  });
});
