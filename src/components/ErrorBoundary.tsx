import { Component, type ErrorInfo, type ReactNode } from "react";
import { t } from "../lib/i18n";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  globalErrors: string[];
}

export default class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  private _onerrorHandler: ((event: ErrorEvent) => void) | null = null;
  private _rejectionHandler: ((event: PromiseRejectionEvent) => void) | null = null;

  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null, globalErrors: [] };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error, globalErrors: [] };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error("ErrorBoundary caught:", error, errorInfo);
    this.props.onError?.(error, errorInfo);
  }

  componentDidMount(): void {
    this._onerrorHandler = (event: ErrorEvent) => {
      const text = event.error?.stack || event.message;
      console.error("Global error:", text);
      this.setState((prev) => ({
        globalErrors: [...prev.globalErrors, text.substring(0, 500)].slice(-5),
      }));
    };
    this._rejectionHandler = (event: PromiseRejectionEvent) => {
      const text = event.reason?.stack || event.reason?.message || String(event.reason);
      console.error("Unhandled rejection:", text);
      this.setState((prev) => ({
        globalErrors: [...prev.globalErrors, text.substring(0, 500)].slice(-5),
      }));
    };
    window.addEventListener("error", this._onerrorHandler);
    window.addEventListener("unhandledrejection", this._rejectionHandler);
  }

  componentWillUnmount(): void {
    if (this._onerrorHandler) window.removeEventListener("error", this._onerrorHandler);
    if (this._rejectionHandler) window.removeEventListener("unhandledrejection", this._rejectionHandler);
  }

  handleRetry = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex flex-col items-center justify-center min-h-[400px] p-8 text-center">
          <div className="w-16 h-16 mb-4 text-red-500">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.5}
              aria-hidden="true"
            >
              <title>{t('error.title')}</title>
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
              />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
            {t('error.page_crashed')}
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mb-6 max-w-md">
            {t('error.description')}
          </p>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={this.handleRetry}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md transition-colors"
            >
              {t('common.retry')}
            </button>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors"
            >
              {t('error.refresh')}
            </button>
          </div>
          {this.state.error && (
            <details className="mt-6 text-left max-w-md w-full">
              <summary className="text-sm text-gray-500 dark:text-gray-400 cursor-pointer hover:text-gray-700 dark:hover:text-gray-200">
                {t('error.details')}
              </summary>
              <pre className="mt-2 p-3 bg-gray-100 dark:bg-gray-800 rounded-md text-xs text-gray-700 dark:text-gray-300 overflow-auto">
                {this.state.error.message}
                {this.state.error.stack && <>{"\n\n"}{this.state.error.stack}</>}
              </pre>
            </details>
          )}
          {this.state.globalErrors.length > 0 && (
            <details className="mt-2 text-left max-w-md w-full">
              <summary className="text-sm text-yellow-600 dark:text-yellow-400 cursor-pointer hover:text-yellow-700 dark:hover:text-yellow-300">
                全局错误 ({this.state.globalErrors.length})
              </summary>
              <pre className="mt-2 p-3 bg-gray-100 dark:bg-gray-800 rounded-md text-xs text-gray-700 dark:text-gray-300 overflow-auto">
                {this.state.globalErrors.join("\n---\n")}
              </pre>
            </details>
          )}
        </div>
      );
    }

    return this.props.children;
  }
}
