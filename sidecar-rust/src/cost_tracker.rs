//! OCR 成本追踪与速率限制。
//!
//! 记录每次 API 调用的后端名称、token 数量、成本和时间戳。
//! 强制执行速率限制：每天最多 100 次调用，调用间隔最少 2 秒。
//!
//! # 用法
//!
//! ```rust
//! use sidecar_rust::cost_tracker::CostTracker;
//!
//! let tracker = CostTracker::new(100, 2.0);
//!
//! // 调用前检查速率限制
//! tracker.check_rate_limit()?;
//!
//! // 成功调用后记录
//! tracker.check_and_record("openai", 765, 0.005)?;
//!
//! // 获取当前统计
//! let stats = tracker.get_stats();
//! ```

use chrono::{Duration as ChronoDuration, TimeZone, Utc};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;
use std::sync::Mutex;
use thiserror::Error;
use tracing::{debug, info, warn};

// ── 类型定义 ──────────────────────────────────────────────────────────────

/// 速率限制错误
#[derive(Debug, Error)]
pub enum RateLimitError {
    /// 每日调用次数已达上限
    #[error("每日调用上限 {daily_limit} 次已达，{retry_after_secs} 秒后重置")]
    DailyLimitExceeded {
        daily_limit: u64,
        retry_after_secs: u64,
    },
    /// 调用间隔过短
    #[error("调用间隔过短，{retry_after_secs} 秒后可重试")]
    IntervalTooShort {
        retry_after_secs: u64,
    },
}

/// 统计信息快照
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StatsSnapshot {
    /// 总 API 调用次数
    pub total_calls: u64,
    /// 总消耗 token 数
    pub total_tokens: u64,
    /// 总估算成本（美元）
    pub estimated_cost_usd: f64,
    /// 今日调用次数
    pub calls_today: u64,
    /// 每日调用上限
    pub daily_limit: u64,
    /// 今日剩余调用次数
    pub remaining_today: u64,
}

/// 单次 OCR API 调用记录
#[derive(Debug, Clone, Serialize, Deserialize)]
struct CallRecord {
    /// 后端名称
    backend: String,
    /// 消耗 token 数
    tokens_used: u64,
    /// 成本（美元）
    cost_usd: f64,
    /// Unix 时间戳（秒）
    timestamp: f64,
}

// ── CostTracker ───────────────────────────────────────────────────────────

/// 线程安全的 OCR 成本追踪器，支持速率限制。
///
/// 速率限制：
/// - 每天最多 100 次调用（UTC）
/// - 调用间隔最少 2 秒
///
/// 记录持久化到 `~/.formulasnap/cost_stats.json`，支持跨进程重启。
/// 超过 24 小时的记录在加载时自动清除。
pub struct CostTracker {
    /// 每日调用上限
    daily_limit: u64,
    /// 最小调用间隔（秒）
    min_interval_secs: f64,
    /// 内部状态（Mutex 保护）
    state: Mutex<TrackerState>,
    /// 持久化文件路径（None 表示禁用持久化）
    data_file: Option<PathBuf>,
}

/// 内部状态（由 Mutex 保护）
struct TrackerState {
    /// 所有调用记录
    records: Vec<CallRecord>,
    /// 上次调用时间戳
    last_call_time: f64,
    /// 待写入记录数
    pending_count: u64,
    /// 上次写入磁盘时间
    last_write_time: f64,
    /// 当前日期字符串（YYYY-MM-DD）
    today_date: String,
    /// 今日调用计数缓存
    today_count: u64,
}

impl CostTracker {
    /// 批量写入阈值：记录数
    const BATCH_COUNT: u64 = 5;
    /// 批量写入阈值：时间间隔（秒）
    const BATCH_INTERVAL: f64 = 30.0;
    /// 记录过期时间：24 小时（秒）
    const EVICTION_SECS: f64 = 24.0 * 60.0 * 60.0;

    /// 创建新的 CostTracker 实例。
    ///
    /// # 参数
    ///
    /// * `daily_limit` - 每日调用上限
    /// * `min_interval_secs` - 最小调用间隔（秒）
    pub fn new(daily_limit: u64, min_interval_secs: f64) -> Self {
        let now = Self::now_secs();
        let today_date = Utc
            .timestamp_opt(now as i64, 0)
            .single()
            .map(|dt| dt.format("%Y-%m-%d").to_string())
            .unwrap_or_default();

        let data_file = dirs::config_dir().map(|mut p| {
            p.push("formulasnap");
            p.push("cost_stats.json");
            p
        });

        let tracker = Self {
            daily_limit,
            min_interval_secs,
            state: Mutex::new(TrackerState {
                records: Vec::new(),
                last_call_time: 0.0,
                pending_count: 0,
                last_write_time: now,
                today_date,
                today_count: 0,
            }),
            data_file,
        };

        // 从磁盘加载历史记录
        tracker.load_from_file();

        tracker
    }

    /// 创建禁用持久化的 CostTracker（用于测试）。
    #[cfg(test)]
    fn new_without_persistence(daily_limit: u64, min_interval_secs: f64) -> Self {
        let now = Self::now_secs();
        let today_date = Utc
            .timestamp_opt(now as i64, 0)
            .single()
            .map(|dt| dt.format("%Y-%m-%d").to_string())
            .unwrap_or_default();

        Self {
            daily_limit,
            min_interval_secs,
            state: Mutex::new(TrackerState {
                records: Vec::new(),
                last_call_time: 0.0,
                pending_count: 0,
                last_write_time: now,
                today_date,
                today_count: 0,
            }),
            data_file: None,
        }
    }

    // ── 速率限制 ──────────────────────────────────────────────────────────

    /// 获取当前 UTC 时间戳（秒，浮点数，纳秒精度）
    fn now_secs() -> f64 {
        let now = Utc::now();
        now.timestamp() as f64 + now.timestamp_subsec_nanos() as f64 / 1_000_000_000.0
    }

    /// 检查是否允许新的 API 调用。
    ///
    /// # 错误
    ///
    /// * `RateLimitError::DailyLimitExceeded` - 每日调用次数已达上限
    /// * `RateLimitError::IntervalTooShort` - 调用间隔过短
    pub fn check_rate_limit(&self) -> Result<(), RateLimitError> {
        let now = Self::now_secs();
        let mut state = self.state.lock().unwrap();

        // 检查最小调用间隔
        if state.last_call_time > 0.0 {
            let elapsed = now - state.last_call_time;
            if elapsed < self.min_interval_secs {
                let retry_after = (self.min_interval_secs - elapsed).ceil() as u64;
                warn!(
                    "速率限制：调用间隔不足（{:.1}s < {:.1}s）",
                    elapsed, self.min_interval_secs
                );
                return Err(RateLimitError::IntervalTooShort { retry_after_secs: retry_after });
            }
        }

        // 检查每日调用上限
        let calls_today = self.count_calls_today(&mut state, now);
        if calls_today >= self.daily_limit {
            let retry_after = self.seconds_until_utc_midnight(now);
            warn!("速率限制：每日调用上限 {} 次已达", self.daily_limit);
            return Err(RateLimitError::DailyLimitExceeded {
                daily_limit: self.daily_limit,
                retry_after_secs: retry_after as u64,
            });
        }

        Ok(())
    }

    /// 原子性地检查速率限制并记录调用。
    ///
    /// 将 `check_rate_limit()` 和记录操作合并为单个原子操作，
    /// 消除并发请求的 TOCTOU 竞态条件。
    ///
    /// # 错误
    ///
    /// * `RateLimitError::DailyLimitExceeded` - 每日调用次数已达上限
    /// * `RateLimitError::IntervalTooShort` - 调用间隔过短
    pub fn check_and_record(
        &self,
        backend: &str,
        tokens_used: u64,
        cost_usd: f64,
    ) -> Result<(), RateLimitError> {
        let now = Self::now_secs();
        let mut state = self.state.lock().unwrap();

        // 检查最小调用间隔
        if state.last_call_time > 0.0 {
            let elapsed = now - state.last_call_time;
            if elapsed < self.min_interval_secs {
                let retry_after = (self.min_interval_secs - elapsed).ceil() as u64;
                warn!(
                    "速率限制：调用间隔不足（{:.1}s < {:.1}s）",
                    elapsed, self.min_interval_secs
                );
                return Err(RateLimitError::IntervalTooShort { retry_after_secs: retry_after });
            }
        }

        // 检查每日调用上限
        let calls_today = self.count_calls_today(&mut state, now);
        if calls_today >= self.daily_limit {
            let retry_after = self.seconds_until_utc_midnight(now);
            warn!("速率限制：每日调用上限 {} 次已达", self.daily_limit);
            return Err(RateLimitError::DailyLimitExceeded {
                daily_limit: self.daily_limit,
                retry_after_secs: retry_after as u64,
            });
        }

        // 记录调用
        let record = CallRecord {
            backend: backend.to_string(),
            tokens_used,
            cost_usd,
            timestamp: now,
        };
        state.records.push(record);
        state.last_call_time = now;
        self.increment_daily_count(&mut state, now);
        self.maybe_save(&mut state, now);

        debug!(
            "记录调用：backend={} tokens={} cost=${:.6}",
            backend, tokens_used, cost_usd
        );

        Ok(())
    }

    // ── 统计 ──────────────────────────────────────────────────────────────

    /// 获取当前成本和速率限制统计。
    pub fn get_stats(&self) -> StatsSnapshot {
        let now = Self::now_secs();
        let mut state = self.state.lock().unwrap();

        let total_calls = state.records.len() as u64;
        let total_tokens: u64 = state.records.iter().map(|r| r.tokens_used).sum();
        let total_cost: f64 = state.records.iter().map(|r| r.cost_usd).sum();
        let calls_today = self.count_calls_today(&mut state, now);

        let remaining = self.daily_limit.saturating_sub(calls_today);

        StatsSnapshot {
            total_calls,
            total_tokens,
            estimated_cost_usd: (total_cost * 1_000_000.0).round() / 1_000_000.0,
            calls_today,
            daily_limit: self.daily_limit,
            remaining_today: remaining,
        }
    }

    // ── 持久化 ──────────────────────────────────────────────────────────

    /// 强制将待写入记录刷入磁盘。
    ///
    /// 应在应用关闭时调用以避免数据丢失。
    pub fn flush(&self) {
        let mut state = self.state.lock().unwrap();
        if state.pending_count > 0 {
            self.save_to_file(&state);
            state.pending_count = 0;
            state.last_write_time = Self::now_secs();
        }
    }

    /// 条件性持久化：根据批量阈值决定是否写入磁盘。
    fn maybe_save(&self, state: &mut TrackerState, now: f64) {
        state.pending_count += 1;
        let elapsed = now - state.last_write_time;
        if state.pending_count >= Self::BATCH_COUNT || elapsed >= Self::BATCH_INTERVAL {
            self.save_to_file(state);
            state.pending_count = 0;
            state.last_write_time = now;
        }
    }

    /// 从 JSON 文件加载历史记录。
    fn load_from_file(&self) {
        let data_file = match &self.data_file {
            Some(p) => p.clone(),
            None => return,
        };

        if !data_file.exists() {
            return;
        }

        let content = match fs::read_to_string(&data_file) {
            Ok(c) => c,
            Err(e) => {
                warn!("读取成本统计文件失败: {}", e);
                return;
            }
        };

        let items: Vec<CallRecord> = match serde_json::from_str(&content) {
            Ok(v) => v,
            Err(e) => {
                warn!("解析成本统计文件失败: {}", e);
                return;
            }
        };

        let now = Self::now_secs();
        let cutoff = now - Self::EVICTION_SECS;

        let mut state = self.state.lock().unwrap();
        let mut loaded = 0;
        for item in items {
            if item.timestamp >= cutoff {
                state.records.push(item);
                loaded += 1;
            }
        }

        // 计算今日调用次数
        let today_start = self.utc_day_start(now);
        state.today_count = state
            .records
            .iter()
            .filter(|r| r.timestamp >= today_start)
            .count() as u64;

        info!("从 {} 加载了 {} 条成本记录", data_file.display(), loaded);
    }

    /// 将记录保存到 JSON 文件。
    fn save_to_file(&self, state: &TrackerState) {
        let data_file = match &self.data_file {
            Some(p) => p.clone(),
            None => return,
        };

        if state.records.is_empty() {
            // 无记录时删除文件
            if data_file.exists() {
                if let Err(e) = fs::remove_file(&data_file) {
                    warn!("删除空成本统计文件失败: {}", e);
                }
            }
            return;
        }

        // 创建目录
        if let Some(parent) = data_file.parent() {
            if let Err(e) = fs::create_dir_all(parent) {
                warn!("创建成本统计目录失败: {}", e);
                return;
            }
        }

        match serde_json::to_string(&state.records) {
            Ok(json) => {
                if let Err(e) = fs::write(&data_file, json) {
                    warn!("写入成本统计文件失败: {}", e);
                }
            }
            Err(e) => {
                warn!("序列化成本统计失败: {}", e);
            }
        }
    }

    // ── 内部辅助 ──────────────────────────────────────────────────────────

    /// 递增每日调用计数器，日期变更时重置。
    ///
    /// 注意：调用时必须已持有锁。
    fn increment_daily_count(&self, state: &mut TrackerState, now: f64) {
        let today_str = Utc
            .timestamp_opt(now as i64, 0)
            .single()
            .map(|dt| dt.format("%Y-%m-%d").to_string())
            .unwrap_or_default();

        if today_str != state.today_date {
            state.today_date = today_str;
            state.today_count = 0;
        }
        state.today_count += 1;
    }

    /// 计算今日调用次数。
    ///
    /// 使用缓存的增量计数器实现 O(1) 查询。
    /// 仅在 UTC 日期变更或清除过期记录时回退到全量扫描。
    ///
    /// 注意：调用时必须已持有锁。
    fn count_calls_today(&self, state: &mut TrackerState, now: f64) -> u64 {
        let today_str = Utc
            .timestamp_opt(now as i64, 0)
            .single()
            .map(|dt| dt.format("%Y-%m-%d").to_string())
            .unwrap_or_default();

        // 日期变更：重新扫描
        if today_str != state.today_date {
            state.today_count = state
                .records
                .iter()
                .filter(|r| {
                    Utc.timestamp_opt(r.timestamp as i64, 0)
                        .single()
                        .map(|dt| dt.format("%Y-%m-%d").to_string())
                        .unwrap_or_default()
                        == today_str
                })
                .count() as u64;
            state.today_date = today_str;
            return state.today_count;
        }

        // 清除过期记录
        let old_count = state.records.len();
        self.evict_old_records(state, now);
        if state.records.len() < old_count {
            let today_start = self.utc_day_start(now);
            state.today_count = state
                .records
                .iter()
                .filter(|r| r.timestamp >= today_start)
                .count() as u64;
        }

        state.today_count
    }

    /// 清除超过 24 小时的记录。
    ///
    /// 注意：调用时必须已持有锁。
    fn evict_old_records(&self, state: &mut TrackerState, now: f64) {
        let cutoff = now - Self::EVICTION_SECS;
        // 记录按时间戳追加排序，可以高效地移除前缀
        if let Some(first_keep) = state.records.iter().position(|r| r.timestamp >= cutoff) {
            if first_keep > 0 {
                state.records.drain(..first_keep);
            }
        } else {
            // 所有记录都已过期
            state.records.clear();
        }
    }

    /// 获取 UTC 一天的开始时间戳。
    fn utc_day_start(&self, timestamp: f64) -> f64 {
        Utc.timestamp_opt(timestamp as i64, 0)
            .single()
            .map(|dt| {
                dt.date_naive()
                    .and_hms_opt(0, 0, 0)
                    .unwrap()
                    .and_utc()
                    .timestamp() as f64
            })
            .unwrap_or(0.0)
    }

    /// 计算距离下一个 UTC 午夜的秒数。
    fn seconds_until_utc_midnight(&self, timestamp: f64) -> f64 {
        let dt = Utc.timestamp_opt(timestamp as i64, 0).single();
        match dt {
            Some(dt) => {
                let next_midnight = (dt + ChronoDuration::days(1))
                    .date_naive()
                    .and_hms_opt(0, 0, 0)
                    .unwrap()
                    .and_utc();
                (next_midnight - dt).num_seconds() as f64
            }
            None => 0.0,
        }
    }
}

// ── 测试 ──────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use std::thread;
    use std::time::Duration;

    /// 测试每日速率限制
    #[test]
    fn test_rate_limit_daily() {
        let tracker = CostTracker::new_without_persistence(3, 0.0);

        // 前 3 次应成功
        assert!(tracker.check_and_record("test", 100, 0.001).is_ok());
        assert!(tracker.check_and_record("test", 100, 0.001).is_ok());
        assert!(tracker.check_and_record("test", 100, 0.001).is_ok());

        // 第 4 次应失败
        let result = tracker.check_and_record("test", 100, 0.001);
        assert!(result.is_err());
        match result.unwrap_err() {
            RateLimitError::DailyLimitExceeded { daily_limit, .. } => {
                assert_eq!(daily_limit, 3);
            }
            _ => panic!("期望 DailyLimitExceeded 错误"),
        }
    }

    /// 测试调用间隔限制
    #[test]
    fn test_rate_limit_interval() {
        let tracker = CostTracker::new_without_persistence(100, 0.1);

        // 第一次调用应成功
        assert!(tracker.check_and_record("test", 100, 0.001).is_ok());

        // 立即再次调用应失败
        let result = tracker.check_and_record("test", 100, 0.001);
        assert!(result.is_err());
        match result.unwrap_err() {
            RateLimitError::IntervalTooShort { retry_after_secs } => {
                assert!(retry_after_secs > 0);
            }
            _ => panic!("期望 IntervalTooShort 错误"),
        }

        // 等待间隔后应成功（多留余量避免 CI 调度抖动）
        thread::sleep(Duration::from_millis(200));
        assert!(tracker.check_and_record("test", 100, 0.001).is_ok());
    }

    /// 测试统计准确性
    #[test]
    fn test_stats_accuracy() {
        let tracker = CostTracker::new_without_persistence(100, 0.0);

        // 初始状态
        let stats = tracker.get_stats();
        assert_eq!(stats.total_calls, 0);
        assert_eq!(stats.total_tokens, 0);
        assert_eq!(stats.estimated_cost_usd, 0.0);
        assert_eq!(stats.calls_today, 0);
        assert_eq!(stats.daily_limit, 100);
        assert_eq!(stats.remaining_today, 100);

        // 记录几次调用
        tracker.check_and_record("openai", 100, 0.005).unwrap();
        tracker.check_and_record("claude", 200, 0.010).unwrap();
        tracker.check_and_record("gemini", 150, 0.008).unwrap();

        let stats = tracker.get_stats();
        assert_eq!(stats.total_calls, 3);
        assert_eq!(stats.total_tokens, 450);
        assert!((stats.estimated_cost_usd - 0.023).abs() < 0.0001);
        assert_eq!(stats.calls_today, 3);
        assert_eq!(stats.daily_limit, 100);
        assert_eq!(stats.remaining_today, 97);
    }
}
