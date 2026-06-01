import { t } from "../lib/i18n";
import CaptureFlow from "../components/CaptureFlow";

export default function HomePage() {
  return (
    <div className="flex flex-col items-center justify-center h-full p-8">
      <div className="text-center space-y-4 mb-8">
        <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
          {t('home.title')}
        </h2>
        <p className="text-gray-500 dark:text-gray-400">
          {t('home.description')}
        </p>
      </div>
      <CaptureFlow />
    </div>
  );
}
