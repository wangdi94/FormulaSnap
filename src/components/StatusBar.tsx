import { useState, useEffect } from "react";
import { listen } from "@tauri-apps/api/event";
import { loadSettings } from "../lib/settings";
import { t } from "../lib/i18n";
import { getBackendLabel } from "../lib/constants";
import { checkSidecarHealth } from "../lib/sidecarClient";

type SidecarStatus = "connecting" | "ready" | "error";

export default function StatusBar() {
  const [backendLabel, setBackendLabel] = useState(getBackendLabel("pix2text"));
  const [sidecarStatus, setSidecarStatus] = useState<SidecarStatus>("connecting");
  const [sidecarError, setSidecarError] = useState<string | null>(null);

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

  // 轮询健康检查（兜底，防止事件丢失）
  useEffect(() => {
    const check = async () => {
      const ok = await checkSidecarHealth();
      if (ok) {
        setSidecarStatus("ready");
        setSidecarError(null);
      }
    };

    // 立即检查一次
    void check();

    // 每 5 秒检查一次（仅在未就绪时）
    const interval = setInterval(() => {
      if (sidecarStatus !== "ready") {
        void check();
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [sidecarStatus]);

  const statusColor =
    sidecarStatus === "ready"
      ? "bg-green-500"
      : sidecarStatus === "error"
        ? "bg-red-500"
        : "bg-yellow-500 animate-pulse";

  const statusText =
    sidecarStatus === "ready"
      ? t("status.ready")
      : sidecarStatus === "error"
        ? t("status.sidecar_error")
        : t("status.sidecar_connecting");

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
}
