//! OCR 结果缓存 — SHA256 键 + LRU 淘汰 + TTL 过期。
//!
//! 基于图片字节的 SHA256 哈希与后端名称组合键，缓存 OCR 识别结果。
//! LRU 淘汰策略配合每个条目的 TTL 过期机制。
//!
//! # 用法
//!
//! ```rust
//! use sidecar_rust::cache::OcrCache;
//!
//! let cache = OcrCache::new(100, 3600.0);
//! let key = OcrCache::hash_bytes(b"image data");
//! // key = "a1b2c3..."
//! // cache.set(format!("{}:pix2text", key), latex, confidence, "pix2text", 150);
//! ```

use lru::LruCache;
use sha2::{Digest, Sha256};
use std::num::NonZeroUsize;
use std::sync::Mutex;
use std::time::{Duration, Instant};

// ── 缓存条目 ────────────────────────────────────────────────────────────────

/// 缓存的 OCR 结果（简化版，不含 cost_estimate）。
#[derive(Debug, Clone)]
pub struct CachedResult {
    /// 识别出的 LaTeX 字符串
    pub latex: String,
    /// 置信度 0.0–1.0，LLM 引擎为 None
    pub confidence: Option<f64>,
    /// 使用的后端名称
    pub backend: String,
    /// 识别耗时（毫秒）
    pub timing_ms: u64,
    /// 条目创建时间
    pub created_at: Instant,
}

/// 内部缓存条目，包裹 CachedResult 与过期时间。
#[derive(Debug, Clone)]
struct CacheEntry {
    result: CachedResult,
    expires_at: Instant,
}

// ── OcrCache ────────────────────────────────────────────────────────────────

/// SHA256 键 LRU 缓存，线程安全（基于 `std::sync::Mutex`）。
pub struct OcrCache {
    /// 最大条目数
    max_size: usize,
    /// 每条目 TTL（秒）
    ttl: f64,
    /// LRU 缓存本体
    inner: Mutex<LruCache<String, CacheEntry>>,
}

impl OcrCache {
    /// 创建新缓存。
    ///
    /// - `max_size`: 最大条目数，默认 100
    /// - `ttl`: 每条目存活时间（秒），默认 3600
    pub fn new(max_size: usize, ttl: f64) -> Self {
        Self {
            max_size,
            ttl,
            inner: Mutex::new(LruCache::new(NonZeroUsize::new(max_size).expect("max_size must be > 0"))),
        }
    }

    // ── 静态方法 ──────────────────────────────────────────────────────────

    /// 返回 `data` 的 SHA256 十六进制摘要。
    pub fn hash_bytes(data: &[u8]) -> String {
        let mut hasher = Sha256::new();
        hasher.update(data);
        let result = hasher.finalize();
        result.iter().map(|b| format!("{b:02x}")).collect()
    }

    // ── 缓存操作 ─────────────────────────────────────────────────────────

    /// 获取缓存条目。命中时提升为最近使用；过期时自动删除并返回 `None`。
    pub fn get(&self, key: &str) -> Option<CachedResult> {
        let mut cache = self.inner.lock().expect("cache lock poisoned");
        let entry = cache.get(key)?;
        if entry.expires_at <= Instant::now() {
            cache.pop(key);
            return None;
        }
        Some(entry.result.clone())
    }

    /// 存储缓存条目。已存在则更新；达到容量时淘汰最久未使用条目。
    pub fn set(
        &self,
        key: String,
        latex: String,
        confidence: Option<f64>,
        backend: &str,
        timing_ms: u64,
    ) {
        let entry = CacheEntry {
            result: CachedResult {
                latex,
                confidence,
                backend: backend.to_string(),
                timing_ms,
                created_at: Instant::now(),
            },
            expires_at: Instant::now() + Duration::from_secs_f64(self.ttl),
        };
        let mut cache = self.inner.lock().expect("cache lock poisoned");
        cache.put(key, entry);
    }

    /// 移除所有由指定后端产生的缓存条目，返回移除数量。
    pub fn invalidate(&self, backend: &str) -> usize {
        let mut cache = self.inner.lock().expect("cache lock poisoned");
        let keys_to_remove: Vec<String> = cache
            .iter()
            .filter(|(_, entry)| entry.result.backend == backend)
            .map(|(key, _)| key.clone())
            .collect();
        let count = keys_to_remove.len();
        for key in &keys_to_remove {
            cache.pop(key);
        }
        count
    }

    /// 清空所有缓存条目。
    pub fn clear(&self) {
        let mut cache = self.inner.lock().expect("cache lock poisoned");
        cache.clear();
    }

    /// 当前缓存条目数。
    pub fn size(&self) -> usize {
        let cache = self.inner.lock().expect("cache lock poisoned");
        cache.len()
    }
}

// ── 测试 ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use std::thread;

    fn make_cache(max_size: usize, ttl_secs: f64) -> OcrCache {
        OcrCache::new(max_size, ttl_secs)
    }

    #[test]
    fn test_hash_bytes() {
        let hash = OcrCache::hash_bytes(b"hello world");
        // SHA256("hello world") = b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9
        assert_eq!(hash.len(), 64);
        assert!(hash.starts_with("b94d27b9"));
    }

    #[test]
    fn test_cache_miss() {
        let cache = make_cache(10, 3600.0);
        assert!(cache.get("nonexistent").is_none());
    }

    #[test]
    fn test_cache_hit() {
        let cache = make_cache(10, 3600.0);
        let key = "test_key:pix2text".to_string();
        cache.set(key.clone(), "x^2".to_string(), Some(0.95), "pix2text", 100);
        let result = cache.get(&key).expect("should hit cache");
        assert_eq!(result.latex, "x^2");
        assert_eq!(result.confidence, Some(0.95));
        assert_eq!(result.backend, "pix2text");
        assert_eq!(result.timing_ms, 100);
    }

    #[test]
    fn test_lru_eviction() {
        let cache = make_cache(2, 3600.0);
        cache.set("k1".into(), "a".into(), None, "engine1", 10);
        cache.set("k2".into(), "b".into(), None, "engine1", 20);
        cache.set("k3".into(), "c".into(), None, "engine1", 30); // evicts k1

        assert!(cache.get("k1").is_none(), "k1 should be evicted");
        assert!(cache.get("k2").is_some(), "k2 should still exist");
        assert!(cache.get("k3").is_some(), "k3 should exist");
        assert_eq!(cache.size(), 2);
    }

    #[test]
    fn test_ttl_expiry() {
        let cache = make_cache(10, 0.1); // 100ms TTL
        cache.set("k1".into(), "x".into(), None, "engine1", 10);

        // Immediate hit
        assert!(cache.get("k1").is_some());

        // Wait for expiry
        thread::sleep(Duration::from_millis(150));
        assert!(cache.get("k1").is_none(), "entry should be expired");
        assert_eq!(cache.size(), 0, "expired entry should be removed");
    }

    #[test]
    fn test_invalidate_by_backend() {
        let cache = make_cache(10, 3600.0);
        cache.set("a:openai".into(), "1".into(), None, "openai", 10);
        cache.set("b:openai".into(), "2".into(), None, "openai", 20);
        cache.set("c:pix2text".into(), "3".into(), None, "pix2text", 30);

        let removed = cache.invalidate("openai");
        assert_eq!(removed, 2);
        assert!(cache.get("a:openai").is_none());
        assert!(cache.get("b:openai").is_none());
        assert!(cache.get("c:pix2text").is_some(), "pix2text entry should remain");
    }

    #[test]
    fn test_clear() {
        let cache = make_cache(10, 3600.0);
        cache.set("k1".into(), "a".into(), None, "e", 10);
        cache.set("k2".into(), "b".into(), None, "e", 20);
        assert_eq!(cache.size(), 2);

        cache.clear();
        assert_eq!(cache.size(), 0);
        assert!(cache.get("k1").is_none());
    }

    #[test]
    fn test_size_tracking() {
        let cache = make_cache(10, 3600.0);
        assert_eq!(cache.size(), 0);

        cache.set("k1".into(), "a".into(), None, "e", 10);
        assert_eq!(cache.size(), 1);

        cache.set("k2".into(), "b".into(), None, "e", 20);
        assert_eq!(cache.size(), 2);

        // Overwrite k1
        cache.set("k1".into(), "c".into(), None, "e2", 30);
        assert_eq!(cache.size(), 2, "overwrite should not increase size");
    }

    #[test]
    fn test_update_existing_key() {
        let cache = make_cache(10, 3600.0);
        cache.set("k1".into(), "old".into(), Some(0.5), "engine1", 10);

        // Update
        cache.set("k1".into(), "new".into(), Some(0.9), "engine2", 20);

        let result = cache.get("k1").expect("should hit");
        assert_eq!(result.latex, "new");
        assert_eq!(result.confidence, Some(0.9));
        assert_eq!(result.backend, "engine2");
        assert_eq!(cache.size(), 1);
    }

    #[test]
    fn test_lru_promotes_on_get() {
        let cache = make_cache(2, 3600.0);
        cache.set("k1".into(), "a".into(), None, "e", 10);
        cache.set("k2".into(), "b".into(), None, "e", 20);

        // Access k1 to promote it
        cache.get("k1");

        // Insert k3 — should evict k2 (least recently used)
        cache.set("k3".into(), "c".into(), None, "e", 30);
        assert!(cache.get("k1").is_some(), "k1 should be promoted, still alive");
        assert!(cache.get("k2").is_none(), "k2 should be evicted");
    }
}
