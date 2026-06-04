#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Build script for FormulaSnap Python sidecar (Linux / macOS)
#
# Usage:
#     cd sidecar && ./build.sh
#
# Output:
#     src-tauri/binaries/formulasnap-sidecar-<target-triple>
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_DIR="$PROJECT_ROOT/src-tauri/binaries"
SPEC_FILE="$SCRIPT_DIR/pyinstaller.spec"
BINARY_NAME="formulasnap-sidecar"

# ---------------------------------------------------------------------------
# Detect target triple
# ---------------------------------------------------------------------------
detect_target_triple() {
    local os arch

    case "$(uname -s)" in
        Linux*)  os="unknown-linux-gnu" ;;
        Darwin*) os="apple-darwin" ;;
        *)
            echo "Error: unsupported OS '$(uname -s)'. Use build.bat on Windows." >&2
            exit 1
            ;;
    esac

    case "$(uname -m)" in
        x86_64)  arch="x86_64" ;;
        aarch64|arm64) arch="aarch64" ;;
        *)
            echo "Error: unsupported architecture '$(uname -m)'." >&2
            exit 1
            ;;
    esac

    echo "${arch}-${os}"
}

TARGET_TRIPLE="$(detect_target_triple)"
OUTPUT_NAME="${BINARY_NAME}-${TARGET_TRIPLE}"

echo "==> Platform:  ${TARGET_TRIPLE}"
echo "==> Output:    ${OUTPUT_DIR}/${OUTPUT_NAME}"
echo ""

# ---------------------------------------------------------------------------
# Clean previous build artifacts
# ---------------------------------------------------------------------------
echo "==> Cleaning previous build artifacts..."
rm -rf "$SCRIPT_DIR/build" "$SCRIPT_DIR/dist"
rm -f "${OUTPUT_DIR}/${OUTPUT_NAME}"

# ---------------------------------------------------------------------------
# Ensure output directory exists
# ---------------------------------------------------------------------------
mkdir -p "$OUTPUT_DIR"

# ---------------------------------------------------------------------------
# Build with PyInstaller
# ---------------------------------------------------------------------------
echo "==> Running PyInstaller..."
cd "$SCRIPT_DIR"
pyinstaller pyinstaller.spec --noconfirm --clean

# ---------------------------------------------------------------------------
# Verify bundle contents (check required modules/libs are inside the binary)
# ---------------------------------------------------------------------------
echo "==> 验证 bundle 内容..."
PYINSTALLER_BINARY="$SCRIPT_DIR/dist/${BINARY_NAME}"
if python -c "from PyInstaller.utils.cliutils import archive_viewer" 2>/dev/null; then
    TOC="$(python -m PyInstaller.utils.cliutils.archive_viewer "$PYINSTALLER_BINARY" -l 2>/dev/null || true)"
    # _ssl: C extension, listed by Python module name (no extension)
    if echo "$TOC" | grep -q -E '\b_ssl\b'; then
        echo "  ✓ _ssl"
    else
        echo "  ⚠ _ssl 未在 bundle 中找到"
    fi
    # libcrypto/libssl: shared library dependencies
    for lib in libcrypto libssl; do
        if echo "$TOC" | grep -q -E "\b${lib}"; then
            echo "  ✓ ${lib}"
        else
            echo "  ⚠ ${lib} 未在 bundle 中找到"
        fi
    done
else
    echo "  ⚠ archive_viewer 不可用，跳过 bundle 验证"
fi
echo "==> Bundle 验证完成"

# ---------------------------------------------------------------------------
# Copy output to Tauri binaries directory
# ---------------------------------------------------------------------------
echo "==> Copying binary to ${OUTPUT_DIR}/"
cp "$SCRIPT_DIR/dist/${BINARY_NAME}" "${OUTPUT_DIR}/${OUTPUT_NAME}"

# Make executable (should already be, but ensure it)
chmod +x "${OUTPUT_DIR}/${OUTPUT_NAME}"

echo ""
echo "==> Build complete: ${OUTPUT_DIR}/${OUTPUT_NAME}"
echo "    File size: $(du -h "${OUTPUT_DIR}/${OUTPUT_NAME}" | cut -f1)"
