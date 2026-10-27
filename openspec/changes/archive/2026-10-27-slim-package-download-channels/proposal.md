# Proposal: 2026-10-27-slim-package-download-channels

## Why

一键包当前有两套并行的打包语义：滚动发布的**瘦包**（不含模型）与刚实现、尚未归档的**内嵌模型分档包**（CI 现场下载模型、分卷发布）。用户已决定放弃内嵌模型路线：

- **交付的一键包 MUST 保持瘦包**（不含 `models/`，约 10 MiB），不再有任何内嵌模型的大包形态（含本地 `--with-models`）；
- **模型改为可下载获得**，并且**下载入口统一到应用内**：首次启动只准备环境，随后页面停在「模型」页，由用户按需下载（有进度条、可取消、可断点续传）；
- **下载渠道明确区分国内网络与国外网络**：国内镜像 `hf-mirror.com`（默认）/ 国际直连 `huggingface.co`，并且这个选择在首启与应用内共享、命令行也认。

现状缺口：Web「模型」页已有「国内镜像 / 国际直连」切换（`download_source` 设置），但首启链路（`start.py` → `bootstrap.py --yes`）会**静默下载 7.3 GiB 核心模型**、不走应用内 UI、也不让用户选渠道；命令行 `tools/hf_download.py` 也不认已保存的渠道。

## What Changes

- **回滚内嵌模型包方向**（撤销 `2026-10-27-oneclick-model-bundles` 的全部落地物）：
  - 删除 `.github/workflows/oneclick-models.yml`、`packaging/build_model_bundle.py`、`tests/test_model_bundle.py`、`packaging/smoke_package.py` 的 `--bundle` / `--parts` 模式、未归档变更目录；
  - `tools/bootstrap.py` 移除 `models/.bundle` 分支（保留「任一引擎就位即跳过核心下载」的健壮性修正）。
- **移除本地大包模式**：`packaging/build_package.py` 删除 `--with-models` / `--platform` 及其模型内嵌、STORED 写入、平台命名逻辑——「一键包」只剩瘦包一种定义。
- **首启只准备环境**：`tools/start.py` 只确保 `.venv` + 依赖 + MLX 运行时（`bootstrap.py --yes --skip-models`），不再下载任何模型；启动后应用发现核心模型缺失时**自动落到「模型」页**并用既有 toast 提示「先下载核心模型，下载源可切换（国内镜像 / 国际直连）」；创建歌曲在缺核心模型时也给出同样的引导。
- **首启渠道选择**：`tools/bootstrap.py` 新增 `--models`（显式下载核心模型）与 `--download-source {mirror,huggingface}`；交互式运行 `--models` 时询问渠道并**持久化到 `web/data/settings.json` 的 `download_source`**（与 Web 模型页同一字段）；`--yes` 默认 `mirror`；已保存渠道不再重复询问。应用内渠道选择沿用既有模型页分段控件。
- **下载器渠道解析**：`tools/hf_download.py` 新增 `--source` / `--endpoint`；端点优先级 CLI > `YUE2_HF_ENDPOINT` > 已保存设置 > 默认 `mirror`；下载失败时打印当前渠道、可切换的另一渠道与切换方式（不做自动跨渠道重试）。
- **Web 首启引导（无视觉变更）**：`/api/state` 增加 `core_installed`；前端在核心模型缺失时自动切到「模型」页并 toast 提示，创建按钮在缺模型时同样引导——仅行为 + i18n 文案，**不新增/不修改任何可见控件样式或布局**（对照 `web-ui-design` 冻结规格的「视觉变更管控」排除项：纯文案/i18n 与不可见行为修复不属于视觉变更）。
- **文档**：`packaging/使用说明.md` 重写首启与下载源章节、删除内嵌模型包章节；`README.md` 一键包段落同步。

## Capabilities

### New Capabilities

- `model-download-channels`：国内/国外两种下载渠道的定义、单一真相持久化（`web/data/settings.json` 的 `download_source`）、CLI / 首启 / Web 的解析优先级与一致性、下载失败时的渠道切换提示。

### Modified Capabilities

- `one-click-packaging`：包内容条款改为「一键包 MUST NOT 含模型（无任何内嵌模型形态）」；首启体验改为「只准备环境 + 应用内下载模型 + 渠道选择」；命名与冒烟删除权重 STORED/zip64 条款；CI 条款删除「含模型大包分卷发布」相关表述。

## Impact

- 删除：`oneclick-models.yml`、`build_model_bundle.py`、`tests/test_model_bundle.py`、`tests/test_bootstrap_bundle.py`、`openspec/changes/2026-10-27-oneclick-model-bundles/`；`smoke_package.py` 回退瘦包冒烟；`bootstrap.py` 移除 `.bundle` 分支。
- 修改：`packaging/build_package.py`（去 `--with-models`）、`tools/hf_download.py`、`tools/bootstrap.py`、`tools/start.py`、`web/server.py`（`core_installed`）、`web/static/app.js`（首启引导，仅行为）、`web/static/i18n.js`（文案）、`packaging/使用说明.md`、`README.md`。
- 新增：`tests/test_download_channels.py`、`tests/test_bootstrap.py`；`tests/test_web_models.py` 增加 `core_installed` 断言。
- 外部动作：删除 GitHub 滚动 release `oneclick-models-latest` 及其约 8 GB 试跑资产（用户已确认）；不创建任何 tag。
- 兼容性：`download_source` 取值（`mirror` | `huggingface`）与既有 Web API / 设置一致；老用户默认 `mirror`，行为不变；瘦包 CI（`oneclick.yml`）流水线不改。
