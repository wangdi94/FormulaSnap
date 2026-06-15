import base64
import time
from unittest.mock import AsyncMock, MagicMock, patch

from sidecar.api.server import _engines, app, register_engine
from sidecar.cache import OcrCache, ocr_cache
from sidecar.ocr_engines.cost_tracker import cost_tracker
from sidecar.ocr_engines.interface import OcrResult


def _make_result(latex: str = "x^2", backend: str = "pix2text", timing_ms: int = 100) -> OcrResult:
    return OcrResult(latex=latex, backend=backend, timing_ms=timing_ms, confidence=0.9)


def _make_image_base64(data: bytes = b"test-image") -> str:
    """Encode raw bytes to base64 string for /api/ocr requests."""
    return base64.b64encode(data).decode()


def _make_engine_mock(latex: str = "x^2", backend: str = "pix2text") -> MagicMock:
    """Build a MagicMock engine whose recognize() returns a plausible result."""
    result = MagicMock()
    result.latex = latex
    result.confidence = 0.95
    result.backend = backend
    result.timing_ms = 100
    result.cost_estimate = None
    engine = MagicMock()
    engine.recognize = AsyncMock(return_value=result)
    return engine


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


class TestCacheIntegration:

    def setup_method(self) -> None:
        _engines.clear()
        ocr_cache.clear()
        cost_tracker.reset()

    def test_cache_integration_hit(self) -> None:
        """Same image twice → second call returns cached result without re-calling engine."""
        from fastapi.testclient import TestClient

        engine = _make_engine_mock()
        register_engine("pix2text", engine)

        client = TestClient(app)
        payload = {"image_base64": _make_image_base64(), "backend": "pix2text"}

        with patch("sidecar.api.server.cost_tracker"):
            r1 = client.post("/api/ocr", json=payload)
            assert r1.status_code == 200

            r2 = client.post("/api/ocr", json=payload)
            assert r2.status_code == 200
            assert r2.json() == r1.json()
            assert engine.recognize.call_count == 1

    def test_cache_integration_miss(self) -> None:
        """Different images → both call engine (no false cache hit)."""
        from fastapi.testclient import TestClient

        engine = _make_engine_mock()
        register_engine("pix2text", engine)

        client = TestClient(app)
        p1 = {"image_base64": _make_image_base64(b"image-alpha"), "backend": "pix2text"}
        p2 = {"image_base64": _make_image_base64(b"image-beta"), "backend": "pix2text"}

        with patch("sidecar.api.server.cost_tracker"):
            client.post("/api/ocr", json=p1)
            client.post("/api/ocr", json=p2)

        assert engine.recognize.call_count == 2

    def test_cache_key_uniqueness(self) -> None:
        """Same image + different backend → separate cache entries, engine called twice."""
        from fastapi.testclient import TestClient

        engine = _make_engine_mock()
        register_engine("pix2text", engine)
        register_engine("openai", engine)

        client = TestClient(app)
        img = _make_image_base64(b"shared-image")
        p1 = {"image_base64": img, "backend": "pix2text"}
        p2 = {"image_base64": img, "backend": "openai"}

        with patch("sidecar.api.server.cost_tracker"):
            client.post("/api/ocr", json=p1)
            client.post("/api/ocr", json=p2)

        assert engine.recognize.call_count == 2

    def test_cache_ttl_expires(self) -> None:
        """Cached entry expires after TTL → engine called again on next request."""
        from fastapi.testclient import TestClient

        import sidecar.api.server as server_mod

        short_cache = OcrCache(max_size=100, ttl=0.2)
        with patch.object(server_mod, "ocr_cache", short_cache):
            engine = _make_engine_mock()
            register_engine("pix2text", engine)

            client = TestClient(app)
            payload = {"image_base64": _make_image_base64(b"ttl-image"), "backend": "pix2text"}

            with patch("sidecar.api.server.cost_tracker"):
                r1 = client.post("/api/ocr", json=payload)
                assert r1.status_code == 200
                assert engine.recognize.call_count == 1

                time.sleep(0.25)

                r2 = client.post("/api/ocr", json=payload)
                assert r2.status_code == 200
                assert engine.recognize.call_count == 2
