import { memo } from 'react';
import { t } from '../../lib/i18n';
import { Section } from './Section';

const APP_VERSION = '0.1.0';

export const AboutSection = memo(function AboutSection() {
  return (
    <Section title={t('settings.about')} description={t('settings.about_description')} icon="ℹ️">
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-600 dark:text-gray-400">{t('settings.app_name')}</span>
          <span className="text-sm font-medium text-gray-900 dark:text-white">FormulaSnap</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-600 dark:text-gray-400">{t('settings.version')}</span>
          <span className="text-sm font-mono text-gray-900 dark:text-white">v{APP_VERSION}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-600 dark:text-gray-400">{t('settings.license')}</span>
          <span className="text-sm text-gray-900 dark:text-white">MIT</span>
        </div>
      </div>
    </Section>
  );
});
