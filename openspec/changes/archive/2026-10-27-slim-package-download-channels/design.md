# Design: 2026-10-27-slim-package-download-channels

## Context

- 官方交付形态是瘦包：`oneclick.yml` 在 CI 构建约 10 MiB 的双平台 zip（启动器 + 使用说明 + 源码 + `docs/style-terms.md`），发布到滚动 release `oneclick-latest`。`packaging/build_package.py` 另有一条本地 `--with-models` 大包通道（用户已决定删除）。
- 首启链路：`start.command` / `start.bat` → `tools/start.py` → 缺环境或缺模型时调 `tools/bootstrap.py --yes`。**旧行为**：`--yes` 会静默下载核心模型（7.3 GiB）+ 交互默认同意 extras/transcribe/MLX（合计约 11 GiB），既没有渠道选择，也不走应用内 UI。
- Web「模型」页已有下载源切换：设置 `download_source`（`mirror` | `huggingface`），持久化于 `web/data/settings.json`；每次下载把对应端点注入子进程的 `YUE2_HF_ENDPOINT`（`web/server.py` 的 `DOWNLOAD_ENDPOINTS` / `DownloadManager.start`），带进度、取消、断点续传。
- 刚合入（未归档）的 `2026-10-27-oneclick-model-bundles` 增加了一整套内嵌模型分档包机制（新 workflow、流式打包、分卷、`.bundle` 标记），用户已决定放弃。

## Goals / Non-Goals

**Goals:**

- 只有一种交付形态：瘦包（不含模型）；模型只能在应用内或命令行**下载**获得。
- 首启体验：启动器只准备环境；用户打开页面即看到模型下载入口与下载源选项（国内/国外），自行选择后下载核心模型。
- 下载渠道单一真相：应用内模型页、首启 CLI、独立命令行下载器共享同一个 `download_source`，优先级明确、行为可预测。
- 清理内嵌模型包的全部代码、文档与 CI 产物。

**Non-Goals:**

- 不自动探测网络所在地（不做测速/GeoIP/自动跨渠道回退）。
- 不更换下载器，不改分块/续传/校验逻辑，不改瘦包 CI 流水线。
- 不新增可见 UI 控件（首启引导仅用既有的视图切换 + toast + i18n 文案）。
- 不引入第三方依赖。

## Decisions

### D1：放弃并回滚内嵌模型包

删除 `oneclick-models.yml`、`build_model_bundle.py`、`tests/test_model_bundle.py`、`smoke_package.py` 的 `--bundle/--parts`、未归档变更目录、`bootstrap.py` 的 `.bundle` 分支，并清理 GitHub release `oneclick-models-latest`。git 历史保留全部实现，日后需要可再提变更。

### D2：删除本地 `--with-models` 大包通道

`build_package.py` 只保留瘦包构建：去掉 `--with-models` / `--platform`、模型内嵌与 STORED 写入、平台命名、`check_models`、`PLATFORMS`/`STORE_SUFFIXES`/`MODEL_EXCLUDE`。理由：与「一键包不含模型」直接冲突，删除后规格、文档、测试都只有一条路径。规格层面 `one-click-packaging` 的包内容条款同步收紧为「MUST NOT 含模型（任何形态）」。

### D3：首启只准备环境，模型在应用内下载

`start.py` 判定 `env_ready()`（`.venv` 解释器存在 **且** `.deps-installed` 标记存在），不满足时执行 `bootstrap.py --yes --skip-models`（venv + 依赖 + Apple Silicon 的 MLX 运行时），**不再触发任何模型下载**；随后无条件启动服务并打开浏览器。`models_ready()` 仅用于终端提示。

理由：把 7.3 GiB 的下载交给应用内 UI，用户能看到进度、可取消、可断点续传、可切换下载源；终端黑窗口里静默下载 11 GiB 是当前体验最差的部分。

### D4：首启引导只做「行为 + 文案」，不碰冻结视觉

`/api/state` 新增 `core_installed`（核心模型文件齐备）。前端启动完成 `applyPreferences()` 后：若 `!core_installed` 且未提示过，则 `showView("models")` 并 `toast(t("models.firstRun"))`（一次会话只提示一次）；`createSong()` 在缺模型时同样切到模型页并 toast `models.coreMissing`。模型页已有下载源分段控件与核心模型下载按钮，无需新增控件。

对照 `web-ui-design` 冻结规格：本变更**没有视觉变更**（无新增/修改控件样式、布局、品牌元素），属「纯文案/i18n + 不可见行为修复」排除项；实施后仍按基线截图人工核查无意外差异。

### D5：渠道选择的持久化与共享（单一真相）

`web/data/settings.json` 的 `download_source` 是唯一真相：

- 应用内模型页：既有分段控件写入该字段；
- `bootstrap.py --models` 交互式询问渠道后写同一字段（合并已有 JSON，不覆盖其他设置）；
- `hf_download.py` 读取该字段作为默认来源之一；
- 无论谁写入，取值域固定 `mirror` | `huggingface`。

### D6：端点解析优先级（`hf_download.py`）

`--endpoint URL` > `--source {mirror,huggingface}` > `YUE2_HF_ENDPOINT` > 已保存 `download_source` > 默认 `mirror`。

Web 下载通过 `YUE2_HF_ENDPOINT` 注入（既有语义保留），因此 Web 的选择永远生效；手动运行 `python tools/hf_download.py core` 会跟随应用内已保存渠道；显式参数用于一次性覆盖且不落盘。

### D7：CLI 首启渠道询问的边界

`bootstrap.py` 默认（启动器路径）不询问渠道、不下载模型，只打印指引。只有用户显式 `--models`（或 `--extras/--transcribe/--mlx`）时才询问/使用渠道：交互式提问（已保存则直接沿用并打印）、`--yes` 默认保存值或 `mirror`；`--download-source` 一次性覆盖。这样「双击启动器」与「终端全量安装」两条路径都简单可预期。

### D8：失败处理——提示而非自动重试

下载失败时 `hf_download.py` 打印当前渠道、另一渠道与切换方法（`--source` / 应用「模型」页），已落盘分片保留以续传；MUST NOT 自动跨渠道重试（会掩盖真实网络问题、放大下载时长）。

### D9：保留与内嵌包无关的健壮性改进

`any_engine_ready` / `mlx_variants`（任一引擎就位即跳过核心下载）、`mlx-*` 模式拉取 MLX 推理代码、`vae` 细粒度模式：都是与打包形态无关的通用能力，保留。

## Risks / Trade-offs

- [用户双击后先进「模型」页、要等 7.3 GiB 下载才能生成] → 页面内进度/取消/续传/切换源体验优于终端；使用说明首屏写明「首次使用需下载核心模型」；终端也会打印同一提示。
- [bootstrap 写 `web/data/settings.json` 与 Web 端并发写] → 只在交互式 `--models` 路径写入，且写入是原子替换（tmp + replace），实际场景（安装期间 Web 未运行）无竞争。
- [老用户已习惯 `--yes` 会装好一切] → 文档更新为 `--models --extras --transcribe --mlx`；`--yes` 现在只准备环境，属刻意的行为变更（在一键包语境下更合理）。
- [删除大包能力后离线分发场景变弱] → 模型仍可 `python tools/hf_download.py ...` 下载后自行拷贝 `models/`；不再维护第二套打包代码。
- [删除未归档变更与 release 资产不可逆] → git 历史保留代码；release 仅含两档试跑产物，正式发布 `oneclick-latest` 不受影响。

## Migration Plan

1. 回滚内嵌模型包（代码/测试/文档/未归档变更目录）。
2. `build_package.py` 去 `--with-models`；`smoke_package.py` 回退瘦包冒烟。
3. 渠道解析（`hf_download.py`）+ 首启环境化（`bootstrap.py` / `start.py`）+ `core_installed` 与前端引导。
4. 文档更新（使用说明 / README）。
5. 测试与验证：新增渠道/首启单测、全量 `pytest`、`actionlint`、`openspec validate --strict`、本地构建瘦包、push 后 `oneclick.yml` CI 绿。
6. 删除 GitHub release `oneclick-models-latest`；归档本变更。

## Open Questions

无（B 方案、删除 `--with-models`、删除滚动 release 均已由用户确认）。
