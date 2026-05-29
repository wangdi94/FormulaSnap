# 打包构建指南

本文档记录 FormulaSnap 桌面应用的完整打包流程，涵盖 Windows、macOS 平台构建，Python sidecar 的 PyInstaller 打包，以及 CI/CD 发布流程。

## 前置要求

### 通用依赖

| 工具 | 最低版本 | 用途 |
|------|---------|------|
| Node.js | 20+ | 前端构建 |
| pnpm | 8+ | 包管理器 |
| Rust | 1.70+ | Tauri 后端编译 |
| Python | 3.10+ | Sidecar 打包 |
| PyInstaller | 6+ | Python 可执行文件打包 |

### 安装 PyInstaller

```bash
pip install pyinstaller
```

### 平台特定要求

**Windows:**
- Visual Studio Build Tools（C++ 桌面开发工作负载）
- WebView2（Windows 10 1803+ 自带）

**macOS:**
- Xcode Command Line Tools: `xcode-select --install`
- Apple Developer 账号（代码签名和公证需要）

## PyInstaller 构建

Sidecar 是一个独立的 Python 进程，负责 OCR 引擎调度。打包后生成单文件可执行程序，由 Tauri 通过 `externalBin` 机制调用。

### 构建脚本

项目提供两个平台构建脚本：

- `sidecar/build.sh` — Linux 和 macOS
- `sidecar/build.bat` — Windows

### 手动构建步骤

```bash
cd sidecar
pyinstaller pyinstaller.spec --noconfirm --clean
```

输出文件位于 `sidecar/dist/formulasnap-sidecar`。

### 使用构建脚本

**Linux / macOS:**

```bash
cd sidecar
chmod +x build.sh
./build.sh
```

**Windows:**

```cmd
cd sidecar
build.bat
```

构建脚本自动完成以下操作：
1. 检测当前平台的 target triple（如 `x86_64-unknown-linux-gnu`）
2. 清理上一次的 `build/` 和 `dist/` 目录
3. 运行 PyInstaller 打包
4. 将产物复制到 `src-tauri/binaries/` 并重命名为带平台后缀的文件名

### 产物命名规则

Tauri 要求 sidecar 二进制文件名包含 target triple：

```
formulasnap-sidecar-<arch>-<os>
```

示例：
- `formulasnap-sidecar-x86_64-pc-windows-msvc.exe`
- `formulasnap-sidecar-x86_64-apple-darwin`
- `formulasnap-sidecar-aarch64-apple-darwin`
- `formulasnap-sidecar-x86_64-unknown-linux-gnu`

### pyinstaller.spec 配置说明

spec 文件定义了打包参数：

- **入口点**: `sidecar/main.py`
- **模式**: 单文件（`onefile`），所有依赖打包进一个可执行文件
- **hiddenimports**: 显式声明了 uvicorn、fastapi、pix2text、onnxruntime 等模块，避免 PyInstaller 自动分析遗漏
- **console**: 设为 `True`，便于调试时查看日志输出
- **upx**: 启用 UPX 压缩减小文件体积

如果添加了新的 Python 依赖，需要在 `pyinstaller.spec` 的 `hiddenimports` 中补充对应模块。

## Windows 打包

### 完整流程

```bash
# 1. 构建前端
pnpm install
pnpm build

# 2. 构建 sidecar
cd sidecar
build.bat
cd ..

# 3. 构建 Tauri 应用
cd src-tauri
cargo tauri build
```

### 产物位置

Tauri 构建完成后，安装包位于：

```
src-tauri/target/release/bundle/
├── msi/
│   └── FormulaSnap_0.1.0_x64.msi
├── nsis/
│   └── FormulaSnap_0.1.0_x64-setup.exe
└── exe/
```

### 代码签名（可选）

Windows 代码签名需要 PFX 证书文件。设置环境变量后 Tauri 会自动签名：

```powershell
$env:TAURI_SIGNING_PRIVATE_KEY = "path/to/certificate.pfx"
$env:TAURI_SIGNING_PRIVATE_KEY_PASSWORD = "your-password"
```

## macOS 打包

### 完整流程

```bash
# 1. 构建前端
pnpm install
pnpm build

# 2. 构建 sidecar
cd sidecar
chmod +x build.sh
./build.sh
cd ..

# 3. 构建 Tauri 应用
cd src-tauri
cargo tauri build
```

### 产物位置

```
src-tauri/target/release/bundle/
├── dmg/
│   └── FormulaSnap_0.1.0_aarch64.dmg
└── macos/
    └── FormulaSnap.app
```

### 代码签名和公证

macOS 发布应用必须经过代码签名和 Apple 公证，否则用户打开时会遇到"已损坏"提示。

**1. 设置签名证书**

需要 Apple Developer ID Application 证书，导入到钥匙串后设置环境变量：

```bash
export APPLE_CERTIFICATE="Developer ID Application: Your Name (TEAM_ID)"
export APPLE_CERTIFICATE_PASSWORD="certificate-password"
```

**2. 公证**

Tauri v2 支持自动公证，需要 Apple ID 和 App-Specific Password：

```bash
export APPLE_ID="your@apple.id"
export APPLE_PASSWORD="app-specific-password"
export APPLE_TEAM_ID="YOUR_TEAM_ID"
```

运行 `cargo tauri build` 时，Tauri 会自动完成签名和公证流程。

### Universal Binary（可选）

如果需要同时支持 Intel 和 Apple Silicon，可以在两个架构上分别构建后用 `lipo` 合并：

```bash
lipo -create -output formulasnap-sidecar \
    dist/formulasnap-sidecar-x86_64-apple-darwin \
    dist/formulasnap-sidecar-aarch64-apple-darwin
```

## GitHub Actions 发布流程

### CI 工作流

现有 `.github/workflows/ci.yml` 在每次 push 和 PR 时运行：
- **frontend** job: 在三平台运行 `pnpm test`
- **backend** job: 在三平台运行 `pytest`

### 发布工作流

发布工作流在推送 tag 时触发，自动化完整构建和发布流程。

**触发方式：**

```bash
git tag v0.1.0
git push origin v0.1.0
```

**工作流程概要：**

1. 三平台并行构建（ubuntu、windows、macos）
2. 每个平台：安装依赖 → 构建 sidecar → 构建前端 → Tauri 打包
3. 创建 GitHub Release，上传安装包
4. 生成 updater JSON 文件供自动更新使用

**所需 GitHub Secrets：**

| Secret 名称 | 用途 |
|-------------|------|
| `TAURI_SIGNING_PRIVATE_KEY` | Tauri 更新签名私钥 |
| `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` | 私钥密码 |
| `APPLE_CERTIFICATE` | macOS 签名证书（Base64） |
| `APPLE_CERTIFICATE_PASSWORD` | 证书密码 |
| `APPLE_ID` | Apple ID（公证用） |
| `APPLE_PASSWORD` | App-Specific Password |
| `APPLE_TEAM_ID` | Apple 开发团队 ID |

## 密钥管理

### Tauri 更新签名密钥

Tauri 的自动更新机制使用 Ed25519 密钥对签名。`tauri.conf.json` 中配置的 `pubkey` 是公钥，用于验证更新包。

**生成密钥对：**

```bash
cargo tauri signer generate -w ~/.tauri/myapp.key
```

这会输出公钥和保存私钥文件。公钥填入 `tauri.conf.json` 的 `plugins.updater.pubkey`，私钥保存在安全位置。

**私钥使用：**
- CI 环境：存为 GitHub Secret `TAURI_SIGNING_PRIVATE_KEY`
- 本地构建：设置环境变量 `TAURI_SIGNING_PRIVATE_KEY`

### Apple 签名证书

1. 在 Apple Developer 申请 Developer ID Application 证书
2. 下载 .cer 文件，双击导入钥匙串
3. 从钥匙串导出 .p12 文件
4. Base64 编码后存为 GitHub Secret

```bash
base64 -i certificate.p12 | pbcopy  # macOS
```

### API 密钥

OCR 引擎的 API 密钥（Mathpix、OpenAI、Claude、Gemini）存储在系统密钥环中，由 Python sidecar 的 keyring 模块管理。打包流程不需要这些密钥。

## 故障排除

### PyInstaller 构建失败

**ModuleNotFoundError: No module named 'xxx'**

PyInstaller 无法自动检测所有隐式导入。将缺失模块添加到 `pyinstaller.spec` 的 `hiddenimports` 列表。

**打包后运行报错缺少动态库**

某些包（如 onnxruntime）包含 .dll/.so 文件，PyInstaller 可能遗漏。在 spec 文件的 `Analysis` 中添加 `binaries` 参数：

```python
import onnxruntime
import os
onnx_dir = os.path.dirname(onnxruntime.__file__)
binaries = [(os.path.join(onnx_dir, '*.so'), 'onnxruntime')]
```

**打包体积过大**

检查是否包含了不需要的大型依赖。在 `excludes` 中排除：

```python
excludes=['tkinter', 'matplotlib', 'scipy']
```

### Tauri 构建失败

**sidecar not found**

确认 sidecar 二进制文件已放在正确位置，文件名匹配 target triple：

```
src-tauri/binaries/formulasnap-sidecar-x86_64-pc-windows-msvc.exe
```

运行 `rustc -vV` 查看当前 target triple。

**WebView2 相关错误**

Windows 上确保系统已安装 WebView2 Runtime。Windows 10 1803+ 通常自带，旧版本需要手动安装。

### macOS 签名问题

**"App is damaged" 错误**

应用未公证或签名无效。检查：
1. 证书是否过期
2. `APPLE_ID` 和 `APPLE_PASSWORD` 是否正确
3. 是否使用了 App-Specific Password（不是账号密码）

临时跳过签名检查（仅开发用）：

```bash
xattr -cr /Applications/FormulaSnap.app
```

### CI/CD 常见问题

**GitHub Actions 中 sidecar 构建超时**

PyInstaller 打包 pix2text + onnxruntime 可能很慢。考虑：
- 使用缓存（`actions/cache` 缓存 PyInstaller 构建目录）
- 增加 timeout 设置

**跨平台构建不一致**

每个平台必须在对应系统上构建。不要尝试在 Linux 上交叉编译 Windows 的 sidecar。

## 环境变量速查

| 变量 | 用途 | 必需 |
|------|------|------|
| `TAURI_SIGNING_PRIVATE_KEY` | 更新包签名私钥 | 发布时 |
| `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` | 私钥密码 | 发布时 |
| `APPLE_CERTIFICATE` | macOS 签名证书（Base64） | macOS 发布 |
| `APPLE_CERTIFICATE_PASSWORD` | 证书密码 | macOS 发布 |
| `APPLE_ID` | Apple ID | macOS 公证 |
| `APPLE_PASSWORD` | App-Specific Password | macOS 公证 |
| `APPLE_TEAM_ID` | Apple 团队 ID | macOS 公证 |
