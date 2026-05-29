# CI修复计划

## TL;DR

> **Quick Summary**: 修复 GitHub Actions CI 全部 6 个 matrix job 的失败 — 前端 pnpm 版本未指定、后端 macOS 测试 mock 不完整、后端 ubuntu/windows pip install 因 torch 过大被取消。
>
> **Deliverables**:
> - `package.json` — 添加 `packageManager` 字段
> - `sidecar/tests/test_claude.py` — 修复 ANTHROPIC_AVAILABLE mock
> - `sidecar/tests/test_gemini.py` — 修复 GEMINI_AVAILABLE mock
> - `sidecar/tests/test_llm_base.py` — 修复 OPENAI_AVAILABLE mock
> - `sidecar/tests/test_pix2text.py` — 修复 validate_config mock
> - `sidecar/pyproject.toml` — pix2text 改为可选 extra
> - `.github/workflows/ci.yml` — 更新安装命令，添加超时
>
> **Estimated Effort**: Quick
> **Parallel Execution**: YES — 全部 7 个任务可并行执行
> **Critical Path**: 无依赖链 — 全部 Wave 1 并行

---

## Context

### 原始请求
CI没通过，制定修复计划 — [GitHub Actions Run #26626989334](https://github.com/wangdi94/FormulaSnap/actions/runs/26626989334)

### 问题诊断

通过分析 CI 日志发现 **3 个独立根因**，导致全部 6 个 matrix job（frontend×3 + backend×3）失败：

| Job | 平台 | 失败步骤 | 根因 |
|-----|------|---------|------|
| frontend | ubuntu/macOS/windows | `pnpm/action-setup@v2` | `package.json` 缺少 `packageManager` 字段 |
| backend | macOS | `pytest` (12 tests) | 测试 mock SDK 但未 mock `*_AVAILABLE` 标志 |
| backend | ubuntu/windows | `pip install` | `pix2text→torch` 过大导致 job 被取消 |

### Metis 审查要点
- 确认了 `*_AVAILABLE` 标志在各引擎中的位置和名称
- 建议不改变引擎业务逻辑，只在测试层修复
- 提醒 `pip install` 取消的确切原因需进一步验证（可能是磁盘空间或 runner 资源限制）
- 强调"定义完成"需明确：CI 全部 6 个 job 通过 = 完成

---

## Work Objectives

### 核心目标
修复 CI 流水线，使 push 到 main 分支时全部 6 个 matrix job 通过。

### 具体交付物
- `package.json` 包含 `"packageManager": "pnpm@11.4.0"`
- 4 个测试文件的 mock 修复
- `pyproject.toml` 依赖结构优化
- `ci.yml` 安装命令更新

### 定义完成
- [x] 本地 `pnpm install && pnpm run test` 通过
- [x] 本地 `pip install -e "./sidecar[dev]" && pytest` 通过
- [ ] GitHub Actions 全部 6 个 job 通过（push 后验证）

### Must Have
- `package.json` 有合法的 `packageManager` 字段
- Claude/Gemini/OpenAI/Pix2Text 引擎测试全部通过（无论 SDK 是否安装）
- CI 后端安装不再因大依赖取消

### Must NOT Have (Guardrails)
- **不修改**任何引擎业务代码（`sidecar/sidecar/ocr_engines/*.py`）
- **不修改** Tauri/Rust 层代码
- **不引入**新的测试框架或测试基础设施
- **不改变**现有测试的断言逻辑（只修复 mock 设置）
- **不删除**任何现有测试用例

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** - ALL verification is agent-executed.

### Test Decision
- **Infrastructure exists**: YES (vitest 前端, pytest 后端)
- **Automated tests**: Tests-after（修复后运行现有测试套件确认）
- **Framework**: vitest + pytest
- **CI 即为最终验证**: push 后 GitHub Actions 全部通过

### QA Policy
- **前端**: 运行 `pnpm run test`（vitest，24 个测试）
- **后端**: 运行 `pytest`（176 个测试）+ 重点运行受影响引擎的测试
- **CI 模拟**: 验证修改后的 ci.yml 安装命令语法正确

---

## Execution Strategy

### Parallel Execution Waves

> 全部 7 个任务互相独立，可在同一 Wave 中并行执行。
> 修改涉及不同文件，无合并冲突风险。

```
Wave 1 (全部并行 — 7 个独立任务):
├── Task 1: package.json — 添加 packageManager [quick]
├── Task 2: test_claude.py — 修复 ANTHROPIC_AVAILABLE mock [quick]
├── Task 3: test_gemini.py — 修复 GEMINI_AVAILABLE mock [quick]
├── Task 4: test_llm_base.py — 修复 OPENAI_AVAILABLE mock [quick]
├── Task 5: test_pix2text.py — 修复 validate_config mock [quick]
├── Task 6: pyproject.toml — pix2text 改为 optional extra [quick]
└── Task 7: ci.yml — 更新安装命令 + pnpm version [quick]

Wave FINAL (After ALL tasks — 4 parallel reviews):
├── Task F1: Plan Compliance Audit (oracle)
├── Task F2: Code Quality Review + 运行测试 (unspecified-high)
├── Task F3: Real Manual QA — 本地模拟 CI 环境 (unspecified-high)
└── Task F4: Scope Fidelity Check (deep)
-> 提交 + push → 观察 GitHub Actions 结果 → 用户确认
```

### Dependency Matrix

所有 7 个任务无依赖关系，全部可并行：

- **1-7**: 无依赖 — 全部可立即开始

### Agent Dispatch Summary

- **Wave 1**: **7** — T1-T7 → `quick`
- **FINAL**: **4** — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

> Implementation + Test = ONE Task. Never separate.
> EVERY task MUST have QA Scenarios.
> Task labels MUST use bare numbers: `1.`, `2.`, `3.` — NOT `T1.`, `Task 1.`

- [x] 1. package.json: 添加 `packageManager` 字段以修复前端 CI

  **What to do**:
  - 在 `package.json` 中 `"version": "0.1.0",` 之后添加 `"packageManager": "pnpm@11.4.0",`
  - 确保 JSON 格式正确（逗号位置正确）

  **Must NOT do**:
  - 不修改其他字段
  - 不添加 `engines` 或其他配置

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 单文件一行修改，无复杂逻辑

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2-7)
  - **Blocks**: None
  - **Blocked By**: None (can start immediately)

  **References**:
  - `package.json:4` — `"version": "0.1.0",` 行后插入新字段
  - `pnpm/action-setup@v2` 文档: 读取 `packageManager` 字段自动确定版本

  **Acceptance Criteria**:
  - [ ] `package.json` 包含 `"packageManager": "pnpm@11.4.0"`
  - [ ] JSON 语法有效: `python3 -c "import json; json.load(open('package.json'))"` 不报错

  **QA Scenarios**:

  ```
  Scenario: package.json 语法有效且包含 packageManager 字段
    Tool: Bash
    Steps:
      1. python3 -c "import json; d=json.load(open('package.json')); assert d.get('packageManager') == 'pnpm@11.4.0', f'Expected pnpm@11.4.0, got {d.get(\"packageManager\")}'"
    Expected Result: 命令成功退出（exit code 0），无输出
    Failure Indicators: AssertionError 或 JSONDecodeError
    Evidence: .omo/evidence/task-1-package-manager.txt
  ```

  **Evidence to Capture**:
  - [ ] `task-1-package-manager.txt` — 验证命令输出

  **Commit**: YES (grouped with Tasks 2-7)
  - Message: `fix(ci): 修复 GitHub Actions CI 全部 6 个 job 失败`
  - Files: `package.json`

- [x] 2. test_claude.py: 修复 ANTHROPIC_AVAILABLE mock — 5 个测试

  **What to do**:
  - 在 `setup_method` 中: `import sidecar.ocr_engines.claude_engine as mod`, 保存 `self._orig_avail = mod.ANTHROPIC_AVAILABLE`，设置 `mod.ANTHROPIC_AVAILABLE = True`
  - 添加 `teardown_method(self)`: `import sidecar.ocr_engines.claude_engine as mod; mod.ANTHROPIC_AVAILABLE = self._orig_avail`
  - 受影响测试（5个，均使用 `@patch("sidecar.ocr_engines.claude_engine.anthropic")`）: `test_recognize_success`, `test_recognize_strips_markdown`, `test_recognize_authentication_error`, `test_recognize_rate_limit_error`, `test_recognize_connection_error`
  - 已有 `test_recognize_package_not_installed` 显式覆盖 `ANTHROPIC_AVAILABLE = False` 并在 finally 中恢复，不受影响
  - `test_recognize_no_key_raises` 空 key 先于 AVAILABLE 检查抛出，不受影响

  **Must NOT do**:
  - 不修改引擎业务代码 `claude_engine.py`
  - 不修改 `test_recognize_package_not_installed`（已有正确的 save/restore）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 单文件修改，模式明确，遵循现有 save/restore 风格

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3-7)
  - **Blocks**: None
  - **Blocked By**: None (can start immediately)

  **References**:
  - `sidecar/tests/test_claude.py:181-192` — 已有的 save/restore 模式参考
  - `sidecar/sidecar/ocr_engines/claude_engine.py:55-56` — `recognize()` 中检查 `ANTHROPIC_AVAILABLE` 的位置
  - `sidecar/sidecar/ocr_engines/claude_engine.py:13-25` — `ANTHROPIC_AVAILABLE` 定义

  **Acceptance Criteria**:
  - [ ] `setup_method` 保存并设置 `ANTHROPIC_AVAILABLE = True`
  - [ ] `teardown_method` 恢复原始值
  - [ ] `pytest sidecar/tests/test_claude.py -v` → 11 passed, 0 failed

  **QA Scenarios**:

  ```
  Scenario: Claude 引擎全部测试通过（含修复）
    Tool: Bash
    Preconditions: Python 环境已安装 sidecar[dev]
    Steps:
      1. cd sidecar && pytest tests/test_claude.py -v --tb=short
      2. 确认 test_recognize_success, test_recognize_strips_markdown, test_recognize_authentication_error, test_recognize_rate_limit_error, test_recognize_connection_error 全部 PASSED
    Expected Result: 11 passed, 0 failed
    Failure Indicators: 任何 FAILED，或含 "Anthropic package not installed" 的 ApiKeyError
    Evidence: .omo/evidence/task-2-claude-tests.txt
  ```

  **Evidence to Capture**:
  - [ ] `task-2-claude-tests.txt` — pytest 完整输出

  **Commit**: YES (grouped with all tasks)
  - Files: `sidecar/tests/test_claude.py`

- [x] 3. test_gemini.py: 修复 GEMINI_AVAILABLE + types mock — 4 个测试

  **What to do**:
  - 在 `setup_method` 中: `import sidecar.ocr_engines.gemini_engine as mod`, 保存 `self._orig_avail = mod.GEMINI_AVAILABLE` 和 `self._orig_types = mod.types`，设置 `mod.GEMINI_AVAILABLE = True` 和 `mod.types = MagicMock()`
  - 添加 `teardown_method(self)` 恢复原始值
  - Gemini 引擎检查 3 个条件（`gemini_engine.py:98`）: `if not GEMINI_AVAILABLE or genai is None or types is None:`
  - `genai` 已被 `@patch("sidecar.ocr_engines.gemini_engine.genai")` mock，但 `GEMINI_AVAILABLE` 和 `types` 需要额外设置
  - 受影响测试（4个）: `test_recognize_success`, `test_recognize_large_image_compressed`, `test_recognize_small_image_not_compressed`, `test_recognize_network_error`

  **Must NOT do**:
  - 不修改引擎业务代码 `gemini_engine.py`
  - 不修改不需要 mock 的测试

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 单文件修改，模式与 Task 2 相同

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-2, 4-7)
  - **Blocks**: None
  - **Blocked By**: None (can start immediately)

  **References**:
  - `sidecar/sidecar/ocr_engines/gemini_engine.py:98` — `recognize()` 中检查 3 个条件
  - `sidecar/sidecar/ocr_engines/gemini_engine.py:13-21` — `GEMINI_AVAILABLE`、`genai`、`types` 定义
  - `sidecar/tests/test_gemini.py:19-21` — 现有 `setup_method`
  - `sidecar/tests/test_claude.py:181-192` — save/restore 模式参考

  **Acceptance Criteria**:
  - [ ] `setup_method` 设置 `GEMINI_AVAILABLE = True` 和 `types = MagicMock()`
  - [ ] `teardown_method` 恢复原始值
  - [ ] `pytest sidecar/tests/test_gemini.py -v` → 10 passed, 0 failed

  **QA Scenarios**:

  ```
  Scenario: Gemini 引擎全部测试通过（含修复）
    Tool: Bash
    Preconditions: Python 环境已安装 sidecar[dev]
    Steps:
      1. cd sidecar && pytest tests/test_gemini.py -v --tb=short
      2. 确认 test_recognize_success, test_recognize_large_image_compressed, test_recognize_small_image_not_compressed, test_recognize_network_error 全部 PASSED
    Expected Result: 10 passed, 0 failed
    Failure Indicators: 任何 FAILED，或含 "google-genai package not installed" 的 ApiKeyError
    Evidence: .omo/evidence/task-3-gemini-tests.txt
  ```

  **Evidence to Capture**:
  - [ ] `task-3-gemini-tests.txt` — pytest 完整输出

  **Commit**: YES (grouped with all tasks)
  - Files: `sidecar/tests/test_gemini.py`

- [x] 4. test_llm_base.py: 修复 OPENAI_AVAILABLE mock — 2 个测试

  **What to do**:
  - 在 `setup_method` 中: `import sidecar.ocr_engines.openai_engine as mod`, 保存 `self._orig_avail = mod.OPENAI_AVAILABLE`，设置 `mod.OPENAI_AVAILABLE = True`
  - 添加 `teardown_method(self)` 恢复原始值
  - 受影响测试（2个，均使用 `@patch('sidecar.ocr_engines.openai_engine.openai')`）: `test_recognize_success`, `test_recognize_strips_markdown`
  - 其余测试（`test_estimate_cost`, `test_validate_config_*`）不调用 `recognize()`，不受影响

  **Must NOT do**:
  - 不修改引擎业务代码 `openai_engine.py`
  - 不修改不需要 mock 的测试

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 单文件修改，模式与 Task 2-3 相同

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-3, 5-7)
  - **Blocks**: None
  - **Blocked By**: None (can start immediately)

  **References**:
  - `sidecar/sidecar/ocr_engines/openai_engine.py:55` — `recognize()` 检查 `if not OPENAI_AVAILABLE or openai is None:`
  - `sidecar/sidecar/ocr_engines/openai_engine.py:14-22` — `OPENAI_AVAILABLE` 定义
  - `sidecar/tests/test_llm_base.py:10-11` — 现有 `setup_method`

  **Acceptance Criteria**:
  - [ ] `setup_method` 设置 `OPENAI_AVAILABLE = True`
  - [ ] `teardown_method` 恢复原始值
  - [ ] `pytest sidecar/tests/test_llm_base.py -v` → 5 passed, 0 failed

  **QA Scenarios**:

  ```
  Scenario: OpenAI 引擎全部测试通过（含修复）
    Tool: Bash
    Preconditions: Python 环境已安装 sidecar[dev]
    Steps:
      1. cd sidecar && pytest tests/test_llm_base.py -v --tb=short
      2. 确认 test_recognize_success, test_recognize_strips_markdown 全部 PASSED
    Expected Result: 5 passed, 0 failed
    Failure Indicators: 任何 FAILED，或含 "OpenAI package not installed" 的 ApiKeyError
    Evidence: .omo/evidence/task-4-openai-tests.txt
  ```

  **Evidence to Capture**:
  - [ ] `task-4-openai-tests.txt` — pytest 完整输出

  **Commit**: YES (grouped with all tasks)
  - Files: `sidecar/tests/test_llm_base.py`

- [x] 5. test_pix2text.py: 修复 validate_config mock — 1 个测试

  **What to do**:
  - 在 `test_validate_config_when_pix2text_not_installed` 测试开头添加模块级变量 mock
  - 保存原始 `PIX2TEXT_AVAILABLE` 和 `Pix2Text`，设为 `False` 和 `None`
  - 在测试末尾/teardown 中恢复原始值
  - 根因: 测试断言 `valid=False` 但 macOS CI 已安装 onnxruntime，`Pix2Text` 存在且 `ort` 可用，导致 `validate_config()` 返回 `valid=True`

  **Must NOT do**:
  - 不修改引擎业务代码 `pix2text_engine.py`
  - 不影响其他 pix2text 测试

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 单测试修改，save/restore 模式明确

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-4, 6-7)
  - **Blocks**: None
  - **Blocked By**: None (can start immediately)

  **References**:
  - `sidecar/tests/test_pix2text.py:122-130` — 失败的测试 `test_validate_config_when_pix2text_not_installed`
  - `sidecar/sidecar/ocr_engines/pix2text_engine.py:127-132` — `validate_config()` 检查 `Pix2Text is None`
  - `sidecar/sidecar/ocr_engines/pix2text_engine.py:26-43` — `PIX2TEXT_AVAILABLE` 和 `Pix2Text` 模块级定义

  **Acceptance Criteria**:
  - [ ] 测试 mock `PIX2TEXT_AVAILABLE = False` 和 `Pix2Text = None`
  - [ ] 测试末尾恢复原始值
  - [ ] `pytest sidecar/tests/test_pix2text.py::TestPix2TextEngine::test_validate_config_when_pix2text_not_installed -v` → PASSED

  **QA Scenarios**:

  ```
  Scenario: pix2text 未安装时 validate_config 返回 invalid
    Tool: Bash
    Preconditions: Python 环境已安装 sidecar[dev]
    Steps:
      1. cd sidecar && pytest tests/test_pix2text.py::TestPix2TextEngine::test_validate_config_when_pix2text_not_installed -v --tb=short
      2. 确认显示 PASSED（无论 pix2text 是否实际安装）
    Expected Result: 1 passed
    Failure Indicators: FAILED，AssertionError "assert True is False"
    Evidence: .omo/evidence/task-5-pix2text-test.txt

  Scenario: pix2text 全部测试仍然通过（含修复后）
    Tool: Bash
    Steps:
      1. cd sidecar && pytest tests/test_pix2text.py -v --tb=short
    Expected Result: 8 passed, 0 failed
    Evidence: .omo/evidence/task-5-pix2text-all.txt
  ```

  **Evidence to Capture**:
  - [ ] `task-5-pix2text-test.txt` — 单测试输出
  - [ ] `task-5-pix2text-all.txt` — 全部测试输出

  **Commit**: YES (grouped with all tasks)
  - Files: `sidecar/tests/test_pix2text.py`

- [x] 6. pyproject.toml: pix2text 改为 optional extra 以解决 pip install 取消

  **What to do**:
  - 在 `sidecar/pyproject.toml` 中将 `pix2text>=1.1` 从 `dependencies` 移到 `[project.optional-dependencies]` 新 extra `pix2text`
  - `onnxruntime>=1.16` 也一并移到 `pix2text` extra（它是 pix2text 的运行时依赖）
  - `dependencies` 中保留 `fastapi`, `uvicorn`, `httpx`, `pydantic`
  - 添加 `pix2text` extra: `pix2text = ["pix2text>=1.1", "onnxruntime>=1.16"]`
  - 根因: `pix2text` 依赖 `torch`（~2.4GB），在免费 GitHub Actions runner 上安装时 job 被取消

  **Must NOT do**:
  - 不删除任何依赖，只是从 required 移到 optional
  - 不改变版本约束
  - 不修改引擎代码中的 import 守卫（已有 `try/except ImportError` 处理）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 单文件配置修改

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-5, 7)
  - **Blocks**: None（Task 7 需要知道 extra 名称，但可并行规划）
  - **Blocked By**: None (can start immediately)

  **References**:
  - `sidecar/pyproject.toml:9-16` — 当前 `dependencies` 列表
  - `sidecar/pyproject.toml:18-19` — 现有 `[project.optional-dependencies]` dev extra
  - `sidecar/sidecar/ocr_engines/pix2text_engine.py:30-43` — import 守卫确认 pix2text/onnxruntime 可选

  **Acceptance Criteria**:
  - [ ] `pix2text` 和 `onnxruntime` 不再在 `dependencies` 中
  - [ ] `[project.optional-dependencies]` 包含 `pix2text = ["pix2text>=1.1", "onnxruntime>=1.16"]`
  - [ ] `pip install -e "./sidecar[dev]"` 不再安装 torch/pix2text（验证无 torch 包）

  **QA Scenarios**:

  ```
  Scenario: 基础安装不包含 pix2text/torch
    Tool: Bash
    Preconditions: 新建临时虚拟环境
    Steps:
      1. python3 -m venv /tmp/venv-test && source /tmp/venv-test/bin/activate
      2. pip install -e "./sidecar[dev]"
      3. python3 -c "import pix2text" 2>&1
    Expected Result: ImportError（pix2text 未安装）
    Evidence: .omo/evidence/task-6-no-pix2text.txt

  Scenario: pix2text extra 安装正常
    Tool: Bash
    Steps:
      1. pip install -e "./sidecar[dev,pix2text]"
      2. python3 -c "from pix2text import Pix2Text; print('pix2text OK')"
    Expected Result: "pix2text OK"
    Evidence: .omo/evidence/task-6-with-pix2text.txt
  ```

  **Evidence to Capture**:
  - [ ] `task-6-no-pix2text.txt` — 基础安装验证
  - [ ] `task-6-with-pix2text.txt` — pix2text extra 安装验证

  **Commit**: YES (grouped with all tasks)
  - Files: `sidecar/pyproject.toml`

- [x] 7. ci.yml: 更新 CI 配置 — pnpm version + pix2text extra + timeout

  **What to do**:
  - **Frontend job**: 在 `pnpm/action-setup@v2` 步骤添加 `version: '11.4.0'`（双重保险，配合 package.json 的 packageManager）
  - **Backend job**: 将 `pip install -e "./sidecar[dev]"` 改为 `pip install -e "./sidecar[dev,pix2text]"`
  - 为 `pip install` 步骤添加 `timeout-minutes: 15`（防止大依赖下载超时）
  - 为 backend job 添加 `fail-fast: false`（一个平台失败不影响其他平台继续运行）

  **Must NOT do**:
  - 不删除任何 CI 步骤
  - 不改变 matrix 平台配置
  - 不添加新的 CI job

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 单文件 CI 配置修改

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-6)
  - **Blocks**: None
  - **Blocked By**: None（extra 名 `pix2text` 已在计划中约定，可立即并行）

  **References**:
  - `.github/workflows/ci.yml:14-22` — frontend job 步骤
  - `.github/workflows/ci.yml:30-35` — backend job 步骤
  - `package.json` — pnpm version 11.4.0
  - `sidecar/pyproject.toml` — `pix2text` extra（Task 6 添加）

  **Acceptance Criteria**:
  - [ ] Frontend job: `pnpm/action-setup@v2` 有 `version: '11.4.0'`
  - [ ] Backend job: 安装命令使用 `"./sidecar[dev,pix2text]"` 并设置 `timeout-minutes: 15`
  - [ ] Backend job: `fail-fast: false`

  **QA Scenarios**:

  ```
  Scenario: CI YAML 语法有效
    Tool: Bash
    Steps:
      1. python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" 2>&1 || echo "YAML parse failed"
    Expected Result: 无错误输出（YAML 解析成功）
    Failure Indicators: "YAML parse failed" 或 Python 异常
    Evidence: .omo/evidence/task-7-ci-yaml.txt

  Scenario: CI 配置完整性检查
    Tool: Bash
    Steps:
      1. grep -c "pnpm/action-setup" .github/workflows/ci.yml
      2. grep "version.*11.4.0" .github/workflows/ci.yml
      3. grep "dev,pix2text" .github/workflows/ci.yml
      4. grep "timeout-minutes" .github/workflows/ci.yml
      5. grep "fail-fast.*false" .github/workflows/ci.yml
    Expected Result: 所有 5 个 grep 都有匹配
    Evidence: .omo/evidence/task-7-ci-config.txt
  ```

  **Evidence to Capture**:
  - [ ] `task-7-ci-yaml.txt` — YAML 语法验证
  - [ ] `task-7-ci-config.txt` — 配置完整性检查

  **Commit**: YES (grouped with all tasks)
  - Files: `.github/workflows/ci.yml`

---

## Final Verification Wave

> 4 review agents run in PARALLEL. ALL must APPROVE.

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search codebase for forbidden patterns. Check evidence files exist in .omo/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `pnpm run test` + `pytest`. Run `npx tsc --noEmit --skipLibCheck`. Review all changed files for AI slop patterns. Confirm no business logic changes in engine files.
  Output: `Frontend Tests [PASS/FAIL] | Backend Tests [PASS/FAIL] | TypeCheck [PASS/FAIL] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Simulate CI environment locally:
  1. `pnpm install && pnpm run test` — 前端测试全通过
  2. `pip install -e "./sidecar[dev]" && pytest -k "claude or gemini or openai or pix2text"` — 受影响引擎测试全通过
  3. `pip install -e "./sidecar[dev,pix2text]" && pytest` — 全部 176 测试通过
  Save to `.omo/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff. Verify 1:1 — everything in spec was built, nothing beyond spec. Check "Must NOT do" compliance. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | VERDICT`

---

## Commit Strategy

- **1-7**: `fix(ci): 修复 GitHub Actions CI 全部 6 个 job 失败`
  - `package.json` — 添加 packageManager
  - `sidecar/tests/test_claude.py` — 修复 ANTHROPIC_AVAILABLE mock
  - `sidecar/tests/test_gemini.py` — 修复 GEMINI_AVAILABLE mock
  - `sidecar/tests/test_llm_base.py` — 修复 OPENAI_AVAILABLE mock
  - `sidecar/tests/test_pix2text.py` — 修复 validate_config mock
  - `sidecar/pyproject.toml` — pix2text 改为 optional extra
  - `.github/workflows/ci.yml` — 更新安装命令
  - Pre-commit: `pnpm run test && cd sidecar && pytest`

---

## Success Criteria

### Verification Commands
```bash
# 前端测试
pnpm install && pnpm run test
# Expected: 24 tests passed

# 后端测试 — 无 pix2text
pip install -e "./sidecar[dev]" && pytest
# Expected: 176 tests passed (非 pix2text 测试全部通过)

# 后端测试 — 含 pix2text（可选）
pip install -e "./sidecar[dev,pix2text]" && pytest
# Expected: 176 tests passed (全部通过)

# TypeScript 类型检查
npx tsc --noEmit --skipLibCheck
# Expected: no errors
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] Frontend: 24 vitest tests pass
- [ ] Backend: 176 pytest tests pass
- [ ] GitHub Actions CI: 6/6 jobs pass
