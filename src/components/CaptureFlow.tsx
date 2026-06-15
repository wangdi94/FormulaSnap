import { useState, useEffect, useCallback, useRef } from "react";
import { listen } from "@tauri-apps/api/event";
import { invoke } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { callOcr, type OcrResponse, type OcrBackend, SidecarError, checkSidecarHealth } from "../lib/sidecarClient";
import { loadSettings } from "../lib/settings";
import { t } from "../lib/i18n";
import { Spinner } from "./Spinner";
import CapturePreview from "./capture/CapturePreview";
import OcrResultDisplay from "./capture/OcrResultDisplay";
import CaptureActions from "./capture/CaptureActions";

type FlowState = "idle" | "selecting" | "capturing" | "ocr-loading" | "result" | "error" | "sidecar-offline";

interface FlowError {
  message: string;
  code?: string;
  retryable: boolean;
}

const SELECTING_TIMEOUT_MS = 15_000;

export function extractSidecarError(detail: unknown): { errorType: string | undefined; message: string } {
  if (detail == null || typeof detail !== 'object') {
    return { errorType: undefined, message: '' };
  }
  const errorType = 'error' in detail && typeof detail.error === 'string' ? detail.error : undefined;
  const message = 'message' in detail && typeof detail.message === 'string' ? detail.message : '';
  return { errorType, message };
}

export function mapSidecarError(err: unknown): FlowError {
  if (err instanceof SidecarError) {
    const { errorType, message: detailMessage } = extractSidecarError(err.detail);
    const message = detailMessage || err.message;

    if (errorType === "API_KEY_ERROR") {
      return { message: t('capture.api_key_error', { message }), code: "API_KEY_ERROR", retryable: false };
    }
    if (errorType === "RATE_LIMIT_ERROR" || errorType === "RATE_LIMIT_EXCEEDED") {
      return { message: t('capture.rate_limit_error', { message }), code: "RATE_LIMIT_ERROR", retryable: true };
    }
    if (errorType === "NETWORK_ERROR") {
      return { message: t('capture.network_error', { message }), code: "NETWORK_ERROR", retryable: true };
    }
    return { message, code: errorType, retryable: true };
  }

  if (err instanceof Error) {
    return { message: err.message, retryable: true };
  }
  return { message: t('capture.unknown_error'), retryable: true };
}

export default function CaptureFlow() {
  const [state, setState] = useState<FlowState>("idle");
  const [imageBase64, setImageBase64] = useState<string | null>(null);
  const [result, setResult] = useState<OcrResponse | null>(null);
  const [error, setError] = useState<FlowError | null>(null);
  const [backend, setBackend] = useState<OcrBackend | 'auto'>("pix2text");
  const [hotkey, setHotkey] = useState<string>("Ctrl+Shift+C");
  const [sidecarErrorDetail, setSidecarErrorDetail] = useState<string | null>(null);
  const ocrAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    loadSettings()
      .then((s) => {
        setBackend(s.default_backend);
        setHotkey(s.hotkey);
      })
      .catch((e) => console.warn("Failed to load backend setting:", e));
  }, []);

  useEffect(() => {
    const unlistenReady = listen("sidecar://ready", () => {
      if (state === "sidecar-offline") {
        setState("idle");
        setSidecarErrorDetail(null);
      }
    });

    const unlistenError = listen<string>("sidecar://error", (event) => {
      setState("sidecar-offline");
      setSidecarErrorDetail(event.payload);
    });

    return () => {
      void unlistenReady.then((fn) => fn());
      void unlistenError.then((fn) => fn());
    };
  }, [state]);

  useEffect(() => {
    const check = async () => {
      const ok = await checkSidecarHealth();
      if (!ok) {
        setState("sidecar-offline");
        setSidecarErrorDetail(t("status.sidecar_connecting"));
      }
    };
    void check();
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
          const base64 = await Promise.race([
            invoke<string>("capture_region_base64", { x, y, width, height }),
            new Promise<never>((_, reject) =>
              setTimeout(() => reject(new Error("截图命令超时")), 15000),
            ),
          ]);
          setImageBase64(base64);
          await runOcr(base64);
        } catch (err) {
          setError(mapSidecarError(err));
          setState("error");
        }
        // 恢复主窗口焦点
        try {
          await getCurrentWindow().show();
          await getCurrentWindow().setFocus();
        } catch (e) {
          console.warn("恢复主窗口焦点失败:", e);
        }
      },
    );
    return () => {
      unlisten.then((fn) => fn());
    };
  }, [runOcr]);

  useEffect(() => {
    const unlisten = listen("selection-cancelled", async () => {
      setState("idle");
      // 恢复主窗口焦点
      try {
        await getCurrentWindow().show();
        await getCurrentWindow().setFocus();
      } catch (e) {
        console.warn("恢复主窗口焦点失败:", e);
      }
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
      setError({ message: t('capture.selection_timeout'), code: "SELECTION_TIMEOUT", retryable: false });
    }, SELECTING_TIMEOUT_MS);
    return () => clearTimeout(timer);
  }, [state]);

  return (
    <div className="flex flex-col items-center w-full max-w-2xl mx-auto space-y-6">
      {state === "sidecar-offline" && (
        <div className="flex flex-col items-center space-y-4 py-12">
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-6 max-w-md">
            <div className="flex items-start space-x-3">
              <svg className="w-6 h-6 text-red-500 mt-0.5 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <title>{t("error.title")}</title>
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                  clipRule="evenodd"
                />
              </svg>
              <div>
                <p className="text-sm font-medium text-red-800 dark:text-red-200">
                  {t("status.sidecar_error")}
                </p>
                <p className="mt-1 text-sm text-red-600 dark:text-red-300">
                  {sidecarErrorDetail ?? t("status.sidecar_connecting")}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {state === "idle" && (
        <div className="flex flex-col items-center space-y-4 py-12">
          <div className="p-12 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
            <p className="text-gray-400 dark:text-gray-500 text-center">
              {t('capture.hotkey_hint', { hotkey })}
            </p>
          </div>
          <button
            type="button"
            onClick={handleManualCapture}
            className="px-6 py-2.5 bg-blue-500 hover:bg-blue-600 text-white rounded-lg transition-colors font-medium"
          >
            {t('capture.select_region')}
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
          <p className="text-gray-500 dark:text-gray-400">{t('capture.drag_hint')}</p>
        </div>
      )}

      {state === "capturing" && (
        <div className="flex flex-col items-center space-y-4 py-12">
          <div className="animate-pulse flex space-x-1">
            <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
            <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
            <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
          </div>
          <p className="text-gray-500 dark:text-gray-400">{t('capture.captured')}</p>
        </div>
      )}

      {state === "ocr-loading" && (
        <div className="flex flex-col items-center space-y-4 py-12" role="status" aria-live="polite">
          <Spinner size="lg" className="text-blue-500" title={t('common.loading')} />
          <p className="text-gray-500 dark:text-gray-400">{t('capture.ocr_loading')}</p>
          {imageBase64 && <CapturePreview imageBase64={imageBase64} variant="loading" />}
        </div>
      )}

      {state === "error" && error && (
        <div className="w-full space-y-4">
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
            <div className="flex items-start space-x-3">
              <svg className="w-5 h-5 text-red-500 mt-0.5 shrink-0" fill="currentColor" viewBox="0 0 20 20" aria-label={t('error.title')}>
                <title>{t('error.title')}</title>
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                  clipRule="evenodd"
                />
              </svg>
              <div className="flex-1">
                <p className="text-sm font-medium text-red-800 dark:text-red-200">{t('capture.recognition_failed')}</p>
                <p className="mt-1 text-sm text-red-600 dark:text-red-300">{error.message}</p>
                {error.code && (
                  <p className="mt-1 text-xs text-red-400 dark:text-red-500 font-mono">{error.code}</p>
                )}
              </div>
            </div>
          </div>
          <CaptureActions
            mode="error"
            retryable={error.retryable}
            onRetry={handleRetry}
            onReset={handleReset}
          />
        </div>
      )}

      {state === "result" && result && (
        <div className="w-full space-y-4">
          <OcrResultDisplay result={result} />

          {imageBase64 && <CapturePreview imageBase64={imageBase64} variant="result" />}

          <CaptureActions mode="result" onReset={handleReset} />
        </div>
      )}
    </div>
  );
}
