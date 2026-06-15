import { t } from "../../lib/i18n";

interface CaptureActionsErrorProps {
  mode: "error";
  retryable: boolean;
  onRetry: () => void;
  onReset: () => void;
}

interface CaptureActionsResultProps {
  mode: "result";
  onReset: () => void;
}

type CaptureActionsProps = CaptureActionsErrorProps | CaptureActionsResultProps;

export default function CaptureActions(props: CaptureActionsProps) {
  if (props.mode === "error") {
    return (
      <div className="flex justify-center gap-3">
        {props.retryable && (
          <button
            type="button"
            onClick={props.onRetry}
            className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-md transition-colors text-sm font-medium"
          >
            {t('common.retry')}
          </button>
        )}
        <button
          type="button"
          onClick={props.onReset}
          className="px-4 py-2 bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200 rounded-md transition-colors text-sm font-medium"
        >
          {t('capture.retake')}
        </button>
      </div>
    );
  }

  return (
    <div className="flex justify-center gap-3">
      <button
        type="button"
        onClick={props.onReset}
        className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-md transition-colors text-sm font-medium"
      >
        {t('capture.new_screenshot')}
      </button>
    </div>
  );
}
