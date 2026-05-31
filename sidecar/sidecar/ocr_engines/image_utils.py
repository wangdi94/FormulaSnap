"""Shared image utilities for OCR engines."""


def detect_mime_type(image: bytes) -> str:
    """Detect image MIME type from magic bytes.

    Returns 'image/png' for PNG, 'image/gif' for GIF, 'image/webp' for WebP,
    and 'image/jpeg' as default fallback.
    """
    if image[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image[:3] == b"GIF":
        return "image/gif"
    if image[:4] == b"RIFF" and image[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"
