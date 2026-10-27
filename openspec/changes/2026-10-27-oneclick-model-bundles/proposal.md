# Proposal: 2026-10-27-oneclick-model-bundles

## Why

当前一键包只有两种形态：本地构建的 slim 源码包（首次启动再下模型）与本地 `--with-models` 全量大包。CI（`oneclick.yml`）只构建 slim 包——受 GitHub Release 单资产 2 GiB 上限与「模型不进 CI」的既有约束所限。用户希望在 GitHub 上直接构建并发布**内嵌模型的双平台一键包**，且按模型大小分档，让收件人开箱即用、免首启下载。

## What Changes

- 新增 GitHub Actions workflow，在 `macos-latest` / `windows-latest` 上构建**内嵌模型的一键包**：CI 现场从 Hugging Face 下载模型（复用 `tools/hf_download.py`，CI 上走 `YUE2_HF_ENDPOINT=https://huggingface.co` 直连），随下随压入 zip（STORED），控制磁盘峰值。
- 模型包按**大小分档**发布（收件人按机器配置选一档，不必下载 26 GB 全量）：
  - macOS（Apple Silicon）：`mini`（MLX 4bit ≈ 4.5 GB zip）、`standard`（MLX 8bit ≈ 5.3 GB，推荐档）、`full`（torch 3B + MLX 三档 + 全部 VAE/LoRA/转录栈 ≈ 26 GB）。
  - win-x64：`standard`（torch core：YuE2-3B + YuE2-Vae ≈ 7.4 GB）、`full`（全部 torch 系模型 ≈ 12.4 GB）。
- 超过 2 GiB 的产物**切分为 ≤1.9 GiB 分卷**上传 Release，附 `.sha256` 清单与合并脚本（macOS `cat`、Windows `copy /b`），使用说明覆盖合并步骤与校验。
- 发布方式参考 xiaoheihe_crawler 的成熟做法：tag（`models-v*`）触发 → 先建**草稿** release → 双平台并行构建 + 冒烟 + 传分卷 → 全部完成后**草稿转正式**；另支持 `workflow_dispatch` 手动构建（产物上传 rolling release `oneclick-models-latest`）。**不挂 push 触发**（私仓 macOS 分钟 10× 计费，大包构建仅在明确发布意图时运行）。
- 冒烟扩展：`packaging/smoke_package.py` 支持模型包模式（zip 条目清单校验模型在位、禁用项缺席、各分卷 sha256 校验），不做全量解压。
- **BREAKING（规格层面）**：`one-click-packaging` 规格中「含模型的大包 MUST NOT 走 GitHub Release」条款改为「大包 MUST 经 ≤2 GiB 分卷后走 GitHub Release」。

## Capabilities

### New Capabilities

- `model-bundle-release`：含模型一键包的分档定义（macOS 三档 / win-x64 两档）、CI 现场下载与流式打包、≤1.9 GiB 分卷切分与 sha256 清单、草稿→正式发布流、使用说明的合并与校验指引。

### Modified Capabilities

- `one-click-packaging`：修改「CI 双平台构建与滚动发布」需求中「含模型的大包 MUST NOT 走 GitHub Release（单资产 2GB 上限）」——大包允许且 MUST 以分卷形式上 Release； slim 包的既有行为不变。

## Impact

- 新增：`.github/workflows/oneclick-models.yml`（或扩展 `oneclick.yml`）、`packaging/build_model_bundle.py`（下载 + 流式打包 + 分卷）、分卷合并脚本（`tools/join_parts.py` 或包内脚本）、`packaging/使用说明.md` 增补。
- 修改：`packaging/build_package.py`（复用其白名单/自检逻辑，必要时抽公共函数）、`packaging/smoke_package.py`（模型包冒烟模式）。
- 复用：`tools/hf_download.py`（模型清单、分块下载、sha256 校验；CI 用 `YUE2_HF_ENDPOINT` 切直连）。
- CI 成本：私仓 macOS runner 10× 分钟计费；`full` 档下载 ≈26 GB，单次发布成本集中在手动/tag 触发，不随 push 发生。
- 风险：GitHub runner 磁盘余量（macOS 镜像可用空间需在构建前 `df` 校验，不足即快速失败）；HF 直连在 CI 的吞吐与重试。
