import { useState, useEffect, useCallback, useRef } from "react";
import { listen } from "@tauri-apps/api/event";
import { invoke } from "@tauri-apps/api/core";
import { callOcr, type OcrResponse, type OcrBackend, SidecarError } from "../lib/sidecarClient";
import { loadSettings } from "../lib/settings";
import { BACKEND_LABELS } from "../lib/constants";
import FormulaPreview from "./FormulaPreview";

type FlowState = "idle" | "selecting" | "capturing" | "ocr-loading" | "result" | "error";

interface FlowError {
  message: string;
  code?: string;
  retryable: boolean;
}

const SELECTING_TIMEOUT_MS = 15_000;

function mapSidecarError(err: unknown): FlowError {
  if (err instanceof SidecarError) {
    const detail = err.detail as Record<string, unknown> | undefined;
    const errorType = detail?.error as string | undefined;
    const message = (detail?.message as string) ?? err.message;

    if (errorType === "API_KEY_ERROR") {
      return { message: `API 密钥错误：${message}`, code: "API_KEY_ERROR", retryable: false };
    }
    if (errorType === "RATE_LIMIT_ERROR" || errorType === "RATE_LIMIT_EXCEEDED") {
      return { message: `请求频率超限：${message}`, code: "RATE_LIMIT_ERROR", retryable: true };
    }
    if (errorType === "NETWORK_ERROR") {
      return { message: `网络错误：${message}`, code: "NETWORK_ERROR", retryable: true };
    }
    return { message, code: errorType, retryable: true };
  }

  if (err instanceof Error) {
    return { message: err.message, retryable: true };
  }
  return { message: "未知错误", retryable: true };
}

export default function CaptureFlow() {
  const [state, setState] = useState<FlowState>("idle");
  const [imageBase64, setImageBase64] = useState<string | null>(null);
  const [result, setResult] = useState<OcrResponse | null>(null);
  const [error, setError] = useState<FlowError | null>(null);
  const [backend, setBackend] = useState<OcrBackend | 'auto'>("pix2text");
  const ocrAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    loadSettings()
      .then((s) => setBackend(s.default_backend))
      .catch((e) => console.warn("Failed to load backend setting:", e));
  }, []);

  const runOcr = useCallback(
    async (base64: string) => {
      setState("ocr-loading");
      setError(null);
      setResult(null);

      const controller = new AbortController();
      ocrAbortRef.current = controller;

      try {
        const ocrResult = await callOcr(base64, backend, { signal: controller.signal });
        setResult(ocrResult);
        setState("result");
      } catch (err) {
        if (controller.signal.aborted) return; // 被取消，不更新状态
        setError(mapSidecarError(err));
        setState("error");
      }
    },
    [backend],
  );

  const handleManualCapture = useCallback(async () => {
    setState("selecting");
    setError(null);
    try {
      await invoke("open_selection_window");
    } catch (err) {
      setError(mapSidecarError(err));
      setState("error");
    }
  }, []);

  useEffect(() => {
    const unlisten = listen("open-selection", () => {
      handleManualCapture();
    });
    return () => {
      unlisten.then((fn) => fn());
    };
  }, [handleManualCapture]);

  useEffect(() => {
    const unlisten = listen<{ x: number; y: number; width: number; height: number }>(
      "selection-result",
      async (event) => {
        const { x, y, width, height } = event.payload;
        setState("capturing");
        try {
          const base64 = await invoke<string>("capture_region_base64", {
            x, y, width, height,
          });
          setImageBase64(base64);
          await runOcr(base64);
        } catch (err) {
          setError(mapSidecarError(err));
          setState("error");
        }
      },
    );
    return () => {
      unlisten.then((fn) => fn());
    };
  }, [runOcr]);

  useEffect(() => {
    const unlisten = listen("selection-cancelled", () => {
      setState("idle");
    });
    return () => {
      unlisten.then((fn) => fn());
    };
  }, []);

  const handleRetry = useCallback(() => {
    if (imageBase64) {
      runOcr(imageBase64);
    }
  }, [imageBase64, runOcr]);

  const handleReset = useCallback(() => {
    ocrAbortRef.current?.abort();
    setState("idle");
    setImageBase64(null);
    setResult(null);
    setError(null);
  }, []);

  useEffect(() => {
    return () => {
      ocrAbortRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    if (state !== "selecting") return;
    const timer = setTimeout(() => {
      setState("idle");
      setError({ message: "区域选择超时，请重试", code: "SELECTION_TIMEOUT", retryable: false });
    }, SELECTING_TIMEOUT_MS);
    return () => clearTimeout(timer);
  }, [state]);

  return (
    <div className="flex flex-col items-center w-full max-w-2xl mx-auto space-y-6">
      {state === "idle" && (
        <div className="flex flex-col items-center space-y-4 py-12">
          <div className="p-12 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
            <p className="text-gray-400 dark:text-gray-500 text-center">
              按 <kbd className="px-2 py-1 bg-gray-100 dark:bg-gray-700 rounded text-sm font-mono">Ctrl+Shift+C</kbd> 截图识别
            </p>
          </div>
          <button
            type="button"
            onClick={handleManualCapture}
            className="px-6 py-2.5 bg-blue-500 hover:bg-blue-600 text-white rounded-lg transition-colors font-medium"
          >
            选择区域截图
          </button>
        </div>
      )}

      {state === "selecting" && (
        <div className="flex flex-col items-center space-y-4 py-12">
          <div className="animate-pulse flex space-x-1">
            <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
            <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
            <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
          </div>
          <p className="text-gray-500 dark:text-gray-400">请在全屏覆盖层中拖拽选择区域...</p>
        </div>
      )}

      {state === "capturing" && (
        <div className="flex flex-col items-center space-y-4 py-12">
          <div className="animate-pulse flex space-x-1">
            <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
            <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
            <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
          </div>
          <p className="text-gray-500 dark:text-gray-400">截图完成，正在识别...</p>
        </div>
      )}

      {state === "ocr-loading" && (
        <div className="flex flex-col items-center space-y-4 py-12" role="status" aria-live="polite">
          <svg
            className="animate-spin h-8 w-8 text-blue-500"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            aria-label="加载中"
          >
            <title>加载中</title>
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
          <p className="text-gray-500 dark:text-gray-400">正在调用 OCR 识别...</p>
          {imageBase64 && (
            <img
              src={`data:image/png;base64,${imageBase64}`}
              alt="截图预览"
              className="max-w-xs max-h-32 object-contain rounded border border-gray-200 dark:border-gray-700 opacity-60"
            />
          )}
        </div>
      )}

      {state === "error" && error && (
        <div className="w-full space-y-4">
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
            <div className="flex items-start space-x-3">
              <svg className="w-5 h-5 text-red-500 mt-0.5 shrink-0" fill="currentColor" viewBox="0 0 20 20" aria-label="错误">
                <title>错误</title>
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                  clipRule="evenodd"
                />
              </svg>
              <div className="flex-1">
                <p className="text-sm font-medium text-red-800 dark:text-red-200">识别失败</p>
                <p className="mt-1 text-sm text-red-600 dark:text-red-300">{error.message}</p>
                {error.code && (
                  <p className="mt-1 text-xs text-red-400 dark:text-red-500 font-mono">{error.code}</p>
                )}
              </div>
            </div>
          </div>
          <div className="flex justify-center gap-3">
            {error.retryable && (
              <button
                type="button"
                onClick={handleRetry}
                className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-md transition-colors text-sm font-medium"
              >
                重试
              </button>
            )}
            <button
              type="button"
              onClick={handleReset}
              className="px-4 py-2 bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200 rounded-md transition-colors text-sm font-medium"
            >
              重新截图
            </button>
          </div>
        </div>
      )}

      {state === "result" && result && (
        <div className="w-full space-y-4">
          <FormulaPreview latex={result.latex} readOnly={false} />

          <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4 space-y-2">
            <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              <div className="text-gray-500 dark:text-gray-400">后端</div>
              <div className="text-gray-900 dark:text-gray-100 font-medium">
                {BACKEND_LABELS[result.backend] ?? result.backend}
              </div>

              <div className="text-gray-500 dark:text-gray-400">置信度</div>
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

              <div className="text-gray-500 dark:text-gray-400">耗时</div>
              <div className="text-gray-900 dark:text-gray-100 font-medium">{result.timing_ms} ms</div>

              {result.cost_estimate?.estimated_cost_usd != null && result.cost_estimate.estimated_cost_usd > 0 && (
                <>
                  <div className="text-gray-500 dark:text-gray-400">费用</div>
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

          {imageBase64 && (
            <details className="group">
              <summary className="cursor-pointer text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors">
                截图预览
              </summary>
              <img
                src={`data:image/png;base64,${imageBase64}`}
                alt="截图"
                className="mt-2 max-w-full rounded border border-gray-200 dark:border-gray-700"
              />
            </details>
          )}

          <div className="flex justify-center gap-3">
            <button
              type="button"
              onClick={handleReset}
              className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-md transition-colors text-sm font-medium"
            >
              新截图
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
