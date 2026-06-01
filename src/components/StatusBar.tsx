import { useState, useEffect } from "react";
import { loadSettings } from "../lib/settings";
import { t } from "../lib/i18n";
import { getBackendLabel } from "../lib/constants";

export default function StatusBar() {
  const [backendLabel, setBackendLabel] = useState(getBackendLabel("pix2text"));

  useEffect(() => {
    loadSettings()
      .then((s) => {
        setBackendLabel(getBackendLabel(s.default_backend));
      })
      .catch(() => {
        /* 保持默认值 */
      });
  }, []);

  return (
    <footer className="bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 px-4 py-2 flex items-center justify-between text-sm text-gray-500 dark:text-gray-400">
      <div className="flex items-center space-x-2">
        <span className="w-2 h-2 bg-green-500 rounded-full"></span>
        <span>{t('status.ready')}</span>
      </div>
      <div>
        <span>{backendLabel}</span>
      </div>
    </footer>
  );
}
