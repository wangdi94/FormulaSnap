import { memo } from 'react';
import type { StatsResponse } from '../../lib/sidecarClient';
import { t } from '../../lib/i18n';
import { Section } from './Section';

/* ─── StatCard 子组件 ─── */
const StatCard = memo(function StatCard({
  label,
  value,
  unit,
  highlight,
}: {
  label: string;
  value: string;
  unit: string;
  highlight?: boolean;
}) {
  return (
    <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3 text-center">
      <div className={`text-lg font-semibold font-mono ${highlight ? 'text-blue-600 dark:text-blue-400' : 'text-gray-900 dark:text-white'}`}>
        {value}
      </div>
      <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
        {label}
        <span className="ml-1 text-gray-400 dark:text-gray-500">{unit}</span>
      </div>
    </div>
  );
});

/* ─── 组件 ─── */
interface StatsSectionProps {
  stats: StatsResponse | null;
  statsError: string | null;
  fetchStats: () => void;
}

export const StatsSection = memo(function StatsSection({
  stats,
  statsError,
  fetchStats,
}: StatsSectionProps) {
  return (
    <Section title={t('settings.cost_stats')} description={t('settings.cost_description')} icon="📊">
      {stats ? (
        <div className="grid grid-cols-3 gap-4">
          <StatCard label={t('settings.total_calls')} value={stats.total_calls.toLocaleString()} unit={t('settings.calls_unit')} />
          <StatCard label={t('settings.total_tokens')} value={stats.total_tokens.toLocaleString()} unit="tokens" />
          <StatCard
            label={t('settings.estimated_cost')}
            value={`$${stats.estimated_cost_usd.toFixed(2)}`}
            unit="USD"
            highlight={stats.estimated_cost_usd > 0}
          />
        </div>
      ) : statsError ? (
        <div className="flex items-center justify-between text-sm">
          <span className="text-red-500 dark:text-red-400">{statsError}</span>
          <button
            type="button"
            onClick={fetchStats}
            className="px-3 py-1 text-xs font-medium text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 transition-colors"
          >
            {t('common.retry')}
          </button>
        </div>
      ) : (
        <div className="text-sm text-gray-400 dark:text-gray-500">{t('settings.loading_stats')}</div>
      )}
    </Section>
  );
});
