"""OCR result cache with SHA256 keying and LRU eviction.

Thread-safe in-memory cache for OCR results. Uses SHA256 hash of image
bytes as the cache key, with LRU eviction and per-entry TTL expiration.

Usage:
    from sidecar.cache import ocr_cache
    from sidecar.ocr_engines.interface import OcrResult

    key = OcrCache.hash_bytes(image_bytes)
    cached = ocr_cache.get(key)
    if cached is not None:
        return cached
    result = await engine.recognize(image_bytes, options)
    ocr_cache.set(key, result)
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass

from sidecar.ocr_engines.interface import OcrResult


@dataclass
class _CacheEntry:
    """Internal wrapper holding a cached OcrResult with its expiry timestamp."""

    result: OcrResult
    expires_at: float


class OcrCache:
    """SHA256-keyed LRU cache for OCR results.

    Args:
        max_size: Maximum number of entries before LRU eviction. Default 100.
        ttl: Time-to-live in seconds per entry. Default 3600 (1 hour).
    """

    def __init__(self, max_size: int = 100, ttl: float = 3600.0) -> None:
        self._max_size = max_size
        self._ttl = ttl
        self._lock = threading.Lock()
        # OrderedDict maintains insertion order; move_to_end on access for LRU.
        self._entries: OrderedDict[str, _CacheEntry] = OrderedDict()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @staticmethod
    def hash_bytes(data: bytes) -> str:
        """Return hex SHA256 digest of *data*."""
        return hashlib.sha256(data).hexdigest()

    # ------------------------------------------------------------------
    # Cache operations
    # ------------------------------------------------------------------

    def get(self, key: str) -> OcrResult | None:
        """Return cached result for *key*, or ``None`` on miss / expiry.

        On hit the entry is promoted to most-recently-used.
        """
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if time.monotonic() > entry.expires_at:
                # Expired — remove and report miss.
                del self._entries[key]
                return None
            # Promote to end (most-recently-used).
            self._entries.move_to_end(key)
            return entry.result

    def set(self, key: str, result: OcrResult) -> None:
        """Store *result* under *key*, evicting LRU entry if at capacity."""
        with self._lock:
            if key in self._entries:
                # Update existing entry — promote and replace.
                self._entries[key] = _CacheEntry(
                    result=result, expires_at=time.monotonic() + self._ttl
                )
                self._entries.move_to_end(key)
                return
            # Evict oldest if at capacity.
            while len(self._entries) >= self._max_size:
                self._entries.popitem(last=False)
            self._entries[key] = _CacheEntry(
                result=result, expires_at=time.monotonic() + self._ttl
            )

    def invalidate(self, backend: str) -> int:
        """Remove all cached entries produced by *backend*. Returns count removed."""
        with self._lock:
            to_remove = [k for k, v in self._entries.items() if v.result.backend == backend]
            for k in to_remove:
                del self._entries[k]
            return len(to_remove)

    def clear(self) -> None:
        """Remove all cached entries."""
        with self._lock:
            self._entries.clear()

    @property
    def size(self) -> int:
        """Current number of entries (including possibly expired ones)."""
        with self._lock:
            return len(self._entries)


# Module-level singleton — importable without instantiation ceremony.
ocr_cache = OcrCache()
