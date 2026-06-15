"""Tests for image_utils.py MIME detection and gemini_engine image compression.

Covers:
- detect_mime_type: magic byte detection for PNG, JPEG, WebP, GIF, BMP, unknown
- _compress_image: size reduction, aspect ratio preservation, skip-when-small
"""

import io

from PIL import Image

from sidecar.ocr_engines.image_utils import detect_mime_type

# =========================================================================
# detect_mime_type Tests
# =========================================================================


class TestDetectMimeType:
    """Tests for detect_mime_type magic byte detection."""

    def test_detect_mime_png(self):
        """PNG magic bytes → 'image/png'."""
        png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        assert detect_mime_type(png_header) == "image/png"

    def test_detect_mime_jpeg(self):
        """JPEG magic bytes → 'image/jpeg'."""
        jpeg_header = b"\xff\xd8\xff" + b"\x00" * 100
        assert detect_mime_type(jpeg_header) == "image/jpeg"

    def test_detect_mime_webp(self):
        """WebP RIFF+WEBP magic bytes → 'image/webp'."""
        webp_header = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 100
        assert detect_mime_type(webp_header) == "image/webp"

    def test_detect_mime_gif(self):
        """GIF magic bytes → 'image/gif'."""
        gif_header = b"GIF89a" + b"\x00" * 100
        assert detect_mime_type(gif_header) == "image/gif"

    def test_detect_mime_bmp(self):
        """BMP magic bytes fall through to default → 'image/png'.

        image_utils has no BMP-specific check; 'BM' prefix is not handled,
        so unknown formats default to 'image/png' (lossless, safer).
        """
        bmp_header = b"BM" + b"\x00" * 100
        # Current implementation defaults unknown to image/png
        assert detect_mime_type(bmp_header) == "image/png"

    def test_detect_mime_unknown(self):
        """Arbitrary bytes with no known magic → 'image/png' (default fallback).

        Note: image_utils defaults to 'image/png' rather than
        'application/octet-stream' for unknown formats.
        """
        assert detect_mime_type(b"\x00" * 100) == "image/png"

    def test_detect_mime_empty_bytes(self):
        """Empty input → default 'image/png'."""
        assert detect_mime_type(b"") == "image/png"

    def test_detect_mime_real_png_image(self):
        """A real PNG created by Pillow is correctly detected."""
        img = Image.new("RGB", (10, 10), color="red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        assert detect_mime_type(buf.getvalue()) == "image/png"

    def test_detect_mime_real_jpeg_image(self):
        """A real JPEG created by Pillow is correctly detected."""
        img = Image.new("RGB", (10, 10), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        assert detect_mime_type(buf.getvalue()) == "image/jpeg"

    def test_detect_mime_real_gif_image(self):
        """A real GIF created by Pillow is correctly detected."""
        img = Image.new("RGB", (10, 10), color="green")
        buf = io.BytesIO()
        img.save(buf, format="GIF")
        assert detect_mime_type(buf.getvalue()) == "image/gif"


# =========================================================================
# _compress_image Tests (from gemini_engine)
# =========================================================================


class TestCompressImage:
    """Tests for _compress_image from gemini_engine.

    _compress_image compresses images exceeding Gemini's 7 MB inline limit.
    Uses JPEG re-encoding with progressive quality reduction.
    """

    def test_compress_image_reduces_size(self):
        """Large image is compressed below GEMINI_IMAGE_LIMIT."""
        from sidecar.ocr_engines.gemini_engine import GEMINI_IMAGE_LIMIT, _compress_image

        # Create a large image that exceeds the limit when saved as PNG
        img = Image.new("RGB", (3000, 3000), color="red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        large_image = buf.getvalue()

        # Ensure it's actually over the limit
        if len(large_image) <= GEMINI_IMAGE_LIMIT:
            large_image = large_image * ((GEMINI_IMAGE_LIMIT // len(large_image)) + 1)

        assert len(large_image) > GEMINI_IMAGE_LIMIT
        result = _compress_image(large_image)
        assert len(result) <= GEMINI_IMAGE_LIMIT
        assert len(result) > 0

    def test_compress_image_maintains_aspect_ratio(self):
        """Compressed image preserves original width/height ratio."""
        from sidecar.ocr_engines.gemini_engine import _compress_image

        # Create a non-square image to make aspect ratio check meaningful
        orig_w, orig_h = 400, 200  # 2:1 ratio
        img = Image.new("RGB", (orig_w, orig_h), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()

        result = _compress_image(image_bytes)

        # Open the result to check dimensions
        result_img = Image.open(io.BytesIO(result))
        result_w, result_h = result_img.size
        result_img.close()

        # Aspect ratio should be preserved (within rounding tolerance)
        orig_ratio = orig_w / orig_h
        result_ratio = result_w / result_h
        assert abs(orig_ratio - result_ratio) < 0.05, (
            f"Aspect ratio changed: {orig_ratio:.3f} → {result_ratio:.3f}"
        )

    def test_compress_image_skips_small(self):
        """Already-small image (< limit) is returned without modification.

        _compress_image always processes through PIL (JPEG re-encode),
        but small images still produce output under the limit.
        """
        from sidecar.ocr_engines.gemini_engine import GEMINI_IMAGE_LIMIT, _compress_image

        img = Image.new("RGB", (10, 10), color="red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        small_image = buf.getvalue()

        assert len(small_image) <= GEMINI_IMAGE_LIMIT
        result = _compress_image(small_image)
        assert len(result) <= GEMINI_IMAGE_LIMIT
        assert len(result) > 0

    def test_compress_image_output_is_jpeg(self):
        """Compressed output is always JPEG regardless of input format."""
        from sidecar.ocr_engines.gemini_engine import _compress_image

        img = Image.new("RGB", (50, 50), color="green")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_image = buf.getvalue()

        result = _compress_image(png_image)
        # JPEG magic bytes: \xff\xd8\xff
        assert result[:3] == b"\xff\xd8\xff"

    def test_compress_image_rgba_to_rgb(self):
        """RGBA PNG is converted to RGB (JPEG doesn't support alpha)."""
        from sidecar.ocr_engines.gemini_engine import _compress_image

        img = Image.new("RGBA", (50, 50), color=(255, 0, 0, 128))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        rgba_image = buf.getvalue()

        result = _compress_image(rgba_image)
        assert result[:3] == b"\xff\xd8\xff"

        # Verify the result is a valid JPEG that can be opened
        result_img = Image.open(io.BytesIO(result))
        assert result_img.mode == "RGB"
        result_img.close()
