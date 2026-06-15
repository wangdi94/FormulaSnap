import type { OcrResponse } from "../../types/ocr";
import { getBackendLabel } from "../../lib/constants";
import { t } from "../../lib/i18n";
import FormulaPreview from "../FormulaPreview";

interface OcrResultDisplayProps {
  result: OcrResponse;
}

export default function OcrResultDisplay({ result }: OcrResultDisplayProps) {
  return (
    <>
      <FormulaPreview latex={result.latex} readOnly={false} />

      <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4 space-y-2">
        <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
          <div className="text-gray-500 dark:text-gray-400">{t('capture.backend')}</div>
          <div className="text-gray-900 dark:text-gray-100 font-medium">
            {getBackendLabel(result.backend)}
          </div>

          <div className="text-gray-500 dark:text-gray-400">{t('capture.confidence')}</div>
          <div className="text-gray-900 dark:text-gray-100 font-medium">
            <span
              className={
                result.confidence >= 0.8
                  ? "text-green-600 dark:text-green-400"
                  : result.confidence >= 0.5
                    ? "text-yellow-600 dark:text-yellow-400"
                    : "text-red-600 dark:text-red-400"
              }
            >
              {(result.confidence * 100).toFixed(1)}%
            </span>
          </div>

          <div className="text-gray-500 dark:text-gray-400">{t('capture.timing')}</div>
          <div className="text-gray-900 dark:text-gray-100 font-medium">{result.timing_ms} ms</div>

          {result.cost_estimate?.estimated_cost_usd != null && result.cost_estimate.estimated_cost_usd > 0 && (
            <>
              <div className="text-gray-500 dark:text-gray-400">{t('capture.cost')}</div>
              <div className="text-gray-900 dark:text-gray-100 font-medium">
                ${result.cost_estimate.estimated_cost_usd.toFixed(4)}
                {result.cost_estimate.tokens_used != null && (
                  <span className="text-gray-400 text-xs ml-1">({result.cost_estimate.tokens_used} tokens)</span>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}
