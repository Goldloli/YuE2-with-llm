# Proposal: slim-oneclick-packages

## Why

配套 `model-manager`：模型可在应用内按需下载（含下载源切换）后，一键包无需再携带模型。当前平台大包（22.83 GiB / 11.60 GiB，合计 34 GB）体积不可转发；用户明确要求「一键包中就不用包含模型，不用那么大了」。

## What Changes

（构建体系变更，无视觉变化）

1. **默认构建 = 源码包（不含模型）**：`packaging/build_package.py` 默认（无 `--with-models`）产出**通用单包** `oneclick-packages/yue2-studio-oneclick-<YYYYMMDD>.zip`（约 10 MiB 级，双平台启动器 + 使用说明 + 源码）；
2. **大包模式保留为显式选项**：`--with-models --platform {macos,win-x64}` 维持现状（内嵌模型、平台子目录与命名）——能力不删，仅不再是默认；
3. **删除两个已构建大包**（`oneclick-packages/macos/*` 22.83 GiB、`oneclick-packages/win-x64/*` 11.60 GiB，合计约 34 GB）；
4. **重建源码包并冒烟**（zip 内容抽查、启动器语法、反扫）；
5. **文档更新**：`packaging/使用说明.md` 与 README——模型不再随包；首启 `bootstrap` 下载核心模型（镜像），其余组件（解码器/LoRA/转录/MLX 变体）可在应用内「模型」页按需下载与切换下载源。

非目标（Non-goals）：不删除 `--with-models` 能力；不改 bootstrap 首启流程；不做包内模型增量更新机制。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `one-click-packaging`: 包内容契约修订——默认构建 MUST NOT 包含模型（通用单包）；模型内嵌 MUST 仅在显式 `--with-models` 时发生（并按平台子目录与平台命名产出）。

## Impact

- **代码**：`packaging/build_package.py`（默认分支与输出路径调整）、`packaging/使用说明.md`、README。
- **产物**：删除 34 GB 大包；新源码包约 10 MiB。
- **风险**：低——下载链路已由 model-manager 覆盖，bootstrap 首启流程不变。
