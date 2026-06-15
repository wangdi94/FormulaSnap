import { t } from "../../lib/i18n";

interface CapturePreviewProps {
  imageBase64: string;
  /** "loading" = OCR 进行中，半透明缩略图；"result" = 结果页，可折叠全尺寸预览 */
  variant: "loading" | "result";
}

export default function CapturePreview({ imageBase64, variant }: CapturePreviewProps) {
  if (variant === "loading") {
    return (
      <img
        src={`data:image/png;base64,${imageBase64}`}
        alt={t('capture.screenshot_preview')}
        className="max-w-xs max-h-32 object-contain rounded border border-gray-200 dark:border-gray-700 opacity-60"
      />
    );
  }

  return (
    <details className="group">
      <summary className="cursor-pointer text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors">
        {t('capture.screenshot_preview')}
      </summary>
      <img
        src={`data:image/png;base64,${imageBase64}`}
        alt={t('capture.screenshot')}
        className="mt-2 max-w-full rounded border border-gray-200 dark:border-gray-700"
      />
    </details>
  );
}
