# Proposal: oneclick-ci-release

## Why

用户要求「一键包（Windows + macOS 双平台）直接在 GitHub 上构建」。当前一键包只能在本地构建（`packaging/build_package.py`），没有分发通道；另外远端 CI（上游 `CPU tests` workflow）在首次推送即失败——缺装 `web` 额外依赖（fastapi），Web 测试在收集阶段报 `ModuleNotFoundError`。

## What Changes

1. **新增 `.github/workflows/oneclick.yml`**：`macos-latest` + `windows-latest` 矩阵，各自构建**通用源码包**并按平台命名（`yue2-studio-oneclick-<YYYYMMDD>-{macos,win-x64}.zip`）并生成 `.sha256`；产物发布到**滚动 release `oneclick-latest`**（每期替换旧资产、不堆积）；触发：`push` main（路径过滤）+ 手动 `workflow_dispatch`。
2. **新增 `packaging/smoke_package.py`**：产物冒烟脚本（CI 与本地共用）——校验必需条目、红线（无 `models/`、`web/data/`、`outputs/`、`.git*`、`.venv*`），并写出 sha256 sidecar。
3. **`packaging/build_package.py` Windows 兼容**：Windows 上跳过 POSIX exec-bit 检查；bash 语法检查路径改用正斜杠（Git Bash 兼容）。
4. **`tests.yml` 修复**：安装 `.[test,web]`（补 fastapi / uvicorn / python-multipart），让 Web 测试可在 CI 运行。
5. **`.gitignore` 增补 `dist/`**（CI 资产暂存目录）。

非目标（Non-goals）：不做含模型的大包——GitHub Release 单资产上限 2GB，23GB/12.4GB 不可行；模型分发保持「首启引导下载 + 应用内「模型」页」。不做标签版本化发版（滚动 `oneclick-latest`；tag 发版规则另议）。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `one-click-packaging`: 新增「CI 双平台构建与滚动发布」要求（矩阵构建、平台命名与 sha256、冒烟脚本与红线、滚动 release、Windows 构建兼容）。

## Impact

- **新增**：`.github/workflows/oneclick.yml`、`packaging/smoke_package.py`。
- **修改**：`packaging/build_package.py`（Windows 兼容）、`.github/workflows/tests.yml`（依赖修复）、`.gitignore`（`dist/`）。
- **风险**：低——workflow 首次推送即实际构建并发布；macOS runner 计费分钟约为 1× 的 10 倍，触发已按目录路径过滤。
