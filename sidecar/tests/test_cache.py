import time

from sidecar.cache import OcrCache
from sidecar.ocr_engines.interface import OcrResult


def _make_result(latex: str = "x^2", backend: str = "pix2text", timing_ms: int = 100) -> OcrResult:
    return OcrResult(latex=latex, backend=backend, timing_ms=timing_ms, confidence=0.9)


class TestOcrCache:
    def setup_method(self) -> None:
        self.cache = OcrCache(max_size=5, ttl=3600.0)

    # -- hash_bytes --

    def test_hash_bytes_deterministic(self) -> None:
        data = b"hello image"
        assert OcrCache.hash_bytes(data) == OcrCache.hash_bytes(data)

    def test_hash_bytes_different_inputs(self) -> None:
        assert OcrCache.hash_bytes(b"a") != OcrCache.hash_bytes(b"b")

    # -- get / set --

    def test_cache_miss_returns_none(self) -> None:
        assert self.cache.get("nonexistent") is None

    def test_cache_hit_returns_same_result(self) -> None:
        result = _make_result()
        self.cache.set("k1", result)
        cached = self.cache.get("k1")
        assert cached is result

    def test_cache_hit_promotes_entry(self) -> None:
        for i in range(5):
            self.cache.set(f"k{i}", _make_result(latex=f"f_{i}"))
        self.cache.get("k0")
        self.cache.set("k5", _make_result(latex="f_5"))
        assert self.cache.get("k0") is not None
        assert self.cache.get("k1") is None

    # -- LRU eviction --

    def test_lru_evicts_oldest(self) -> None:
        for i in range(5):
            self.cache.set(f"k{i}", _make_result(latex=f"f_{i}"))
        self.cache.set("k_new", _make_result(latex="f_new"))
        assert self.cache.get("k0") is None
        assert self.cache.get("k_new") is not None

    def test_lru_eviction_order(self) -> None:
        for i in range(5):
            self.cache.set(f"k{i}", _make_result(latex=f"f_{i}"))
        self.cache.get("k1")
        self.cache.set("k5", _make_result(latex="f_5"))
        assert self.cache.get("k1") is not None
        assert self.cache.get("k0") is None

    # -- TTL expiry --

    def test_ttl_expiry(self) -> None:
        cache = OcrCache(max_size=10, ttl=0.1)
        cache.set("k1", _make_result())
        time.sleep(0.15)
        assert cache.get("k1") is None

    def test_ttl_not_expired(self) -> None:
        cache = OcrCache(max_size=10, ttl=10.0)
        cache.set("k1", _make_result())
        assert cache.get("k1") is not None

    # -- invalidate --

    def test_invalidate_by_backend(self) -> None:
        self.cache.set("k1", _make_result(backend="pix2text"))
        self.cache.set("k2", _make_result(backend="mathpix"))
        self.cache.set("k3", _make_result(backend="pix2text"))
        removed = self.cache.invalidate("pix2text")
        assert removed == 2
        assert self.cache.get("k1") is None
        assert self.cache.get("k3") is None
        assert self.cache.get("k2") is not None

    def test_invalidate_unknown_backend_returns_zero(self) -> None:
        self.cache.set("k1", _make_result(backend="pix2text"))
        assert self.cache.invalidate("nonexistent") == 0

    # -- clear --

    def test_clear_removes_all(self) -> None:
        self.cache.set("k1", _make_result())
        self.cache.set("k2", _make_result())
        self.cache.clear()
        assert self.cache.size == 0
        assert self.cache.get("k1") is None

    # -- size --

    def test_size_tracks_entries(self) -> None:
        assert self.cache.size == 0
        self.cache.set("k1", _make_result())
        assert self.cache.size == 1
        self.cache.set("k2", _make_result())
        assert self.cache.size == 2

    # -- update existing key --

    def test_set_existing_key_updates_value(self) -> None:
        r1 = _make_result(latex="old")
        r2 = _make_result(latex="new")
        self.cache.set("k1", r1)
        self.cache.set("k1", r2)
        cached = self.cache.get("k1")
        assert cached is not None
        assert cached.latex == "new"
        assert self.cache.size == 1

    # -- thread safety smoke test --

    def test_concurrent_access_no_crash(self) -> None:
        import threading

        errors: list[Exception] = []

        def writer() -> None:
            try:
                for i in range(50):
                    self.cache.set(f"t{i}", _make_result(latex=f"f{i}"))
            except Exception as e:
                errors.append(e)

        def reader() -> None:
            try:
                for i in range(50):
                    self.cache.get(f"t{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer) for _ in range(3)]
        threads += [threading.Thread(target=reader) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
