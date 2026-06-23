import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { StatsSection } from '../components/settings/StatsSection';
import type { StatsResponse } from '../lib/sidecarClient';

vi.mock('../lib/i18n', () => ({
  t: (key: string) => key,
}));

function makeStats(overrides: Partial<StatsResponse> = {}): StatsResponse {
  return {
    total_calls: 100,
    total_tokens: 50000,
    estimated_cost_usd: 2.5,
    calls_today: 10,
    daily_limit: 100,
    remaining_today: 90,
    ...overrides,
  };
}

describe('StatsSection', () => {
  it('有统计数据时渲染统计卡片', () => {
    render(<StatsSection stats={makeStats()} statsError={null} fetchStats={vi.fn()} />);
    expect(screen.getByText('100')).toBeInTheDocument();
    expect(screen.getByText('50,000')).toBeInTheDocument();
    expect(screen.getByText('$2.50')).toBeInTheDocument();
  });

  it('有错误时显示错误信息和重试按钮', () => {
    const fetchStats = vi.fn();
    render(<StatsSection stats={null} statsError="连接失败" fetchStats={fetchStats} />);
    expect(screen.getByText('连接失败')).toBeInTheDocument();
    const retryBtn = screen.getByText('common.retry');
    expect(retryBtn).toBeInTheDocument();
    fireEvent.click(retryBtn);
    expect(fetchStats).toHaveBeenCalled();
  });

  it('无数据无错误时显示加载中', () => {
    render(<StatsSection stats={null} statsError={null} fetchStats={vi.fn()} />);
    expect(screen.getByText('settings.loading_stats')).toBeInTheDocument();
  });

  it('费用大于 0 时高亮显示', () => {
    render(<StatsSection stats={makeStats({ estimated_cost_usd: 5.0 })} statsError={null} fetchStats={vi.fn()} />);
    const costEl = screen.getByText('$5.00');
    expect(costEl.className).toContain('text-blue');
  });

  it('费用为 0 时不高亮', () => {
    render(<StatsSection stats={makeStats({ estimated_cost_usd: 0 })} statsError={null} fetchStats={vi.fn()} />);
    const costEl = screen.getByText('$0.00');
    expect(costEl.className).not.toContain('text-blue');
  });
});
