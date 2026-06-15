import { useState, useEffect, useMemo, useRef, memo } from "react";
import { listen } from "@tauri-apps/api/event";
import { loadSettings } from "../lib/settings";
import { t } from "../lib/i18n";
import { getBackendLabel } from "../lib/constants";
import { checkSidecarHealth } from "../lib/sidecarClient";

type SidecarStatus = "connecting" | "ready" | "error";

const INITIAL_INTERVAL = 2000;
const MAX_INTERVAL = 30000;

export default memo(function StatusBar() {
  const [backendLabel, setBackendLabel] = useState(getBackendLabel("pix2text"));
  const [sidecarStatus, setSidecarStatus] = useState<SidecarStatus>("connecting");
  const [sidecarError, setSidecarError] = useState<string | null>(null);

  const intervalRef = useRef(INITIAL_INTERVAL);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    loadSettings()
      .then((s) => {
        setBackendLabel(getBackendLabel(s.default_backend));
      })
      .catch(() => {
        /* 保持默认值 */
      });
  }, []);

  // 监听 sidecar 事件
  useEffect(() => {
    const unlistenReady = listen("sidecar://ready", () => {
      setSidecarStatus("ready");
      setSidecarError(null);
    });

    const unlistenError = listen<string>("sidecar://error", (event) => {
      setSidecarStatus("error");
      setSidecarError(event.payload);
    });

    return () => {
      void unlistenReady.then((fn) => fn());
      void unlistenError.then((fn) => fn());
    };
  }, []);

  // 轮询健康检查（指数退避，兜底防止事件丢失）
  useEffect(() => {
    mountedRef.current = true;

    const scheduleNext = (delay: number) => {
      if (!mountedRef.current) return;
      timeoutRef.current = setTimeout(poll, delay);
    };

    const poll = async () => {
      if (!mountedRef.current) return;

      const ok = await checkSidecarHealth();
      if (!mountedRef.current) return;

      if (ok) {
        setSidecarStatus("ready");
        setSidecarError(null);
        intervalRef.current = INITIAL_INTERVAL;
      } else {
        intervalRef.current = Math.min(intervalRef.current * 2, MAX_INTERVAL);
      }

      scheduleNext(intervalRef.current);
    };

    // 立即检查一次
    void poll();

    return () => {
      mountedRef.current = false;
      if (timeoutRef.current !== null) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };
  }, []);

  const statusColor = useMemo(
    () =>
      sidecarStatus === "ready"
        ? "bg-green-500"
        : sidecarStatus === "error"
          ? "bg-red-500"
          : "bg-yellow-500 animate-pulse",
    [sidecarStatus],
  );

  const statusText = useMemo(
    () =>
      sidecarStatus === "ready"
        ? t("status.ready")
        : sidecarStatus === "error"
          ? t("status.sidecar_error")
          : t("status.sidecar_connecting"),
    [sidecarStatus],
  );

  return (
    <footer className="bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 px-4 py-2 flex items-center justify-between text-sm text-gray-500 dark:text-gray-400">
      <div className="flex items-center space-x-2" title={sidecarError ?? undefined}>
        <span className={`w-2 h-2 ${statusColor} rounded-full`}></span>
        <span>{statusText}</span>
      </div>
      <div>
        <span>{backendLabel}</span>
      </div>
    </footer>
  );
});
