# Proposal: model-manager

## Why

用户要求：① 侧栏新增「模型」菜单，页面内可下载各类 YuE2 模型与 LoRA 模型；② 可在页面内设为默认模型；③ 下载源分「国内镜像 / 国际直连」两种、下载时可切换；④ 由此一键包不必再携带模型（配套 `slim-oneclick-packages` 变更）。

现状：模型只能靠 `tools/hf_download.py` 命令行整组下载（core/extras/mlx/transcribe 四组粗粒度），MLX 只有 8-bit；无应用内管理界面。

## What Changes

**本提案包含视觉变更（按 `web-ui-design` 规格显式声明）**：侧栏新增一项导航 + 新增主区页面（均为新增，不改既有组件形态）。

1. **侧栏「模型」导航**：`音乐库` 与用户区之间新增一项（`ph-hard-drives` 图标）；对应 `#view-models` 页面承载于 `#main` 内（符合三栏冻结布局）。
2. **模型清单页（按组展示，逐组件状态与大小）**：

   | 组 | 组件 | 来源与体积 |
   |---|---|---|
   | 核心 | YuE2-3B + YuE2-Vae | m-a-p（约 7.3 GB，必备） |
   | 解码器 | Vae-legacy、Vae-merge 0.666 | m-a-p / Mothersuperior（各约 0.5 GB） |
   | 扩展工具 | realaudio 工具包（head + NAR LoRA） | Mothersuperior（约 0.17 GB） |
   | LoRA 风格 | Death Metal v1、J-Pop T4、Instrumental v3（逐个独立下载） | pduncan / storagejuju / Mothersuperior |
   | 音频转录 | SheetSage2 + MERT-v2-FullSong | m-a-p（约 2.6 GB） |
   | MLX 引擎（macOS） | 8-bit / bf16 / 4-bit 三个独立变体 | ahmadw（约 4.3 / 7.1 / 3.5 GB，均已上架镜像） |

   每行显示：名称、体积、状态（已安装 / 未安装 / 下载中百分比）、操作按钮（下载 / 取消）。
3. **下载源切换**：页面顶部「下载源」分段控件——**国内镜像（hf-mirror.com）** / **国际直连（huggingface.co）**；持久化为 `download_source` 设置（默认镜像），**每次下载使用当前选择**（下载中途也可切换，下一个任务生效）。镜像对本机连通性已验证（hf 直连在本机不通，说明中标注）。
4. **应用内下载机制**：独立下载通道（单并发，**与生成/转录任务并行不阻塞**——下载是 IO 子进程，不占用 GPU/主队列）；复用 `tools/hf_download.py`（新增细粒度组件模式，含 `mlx-bf16` / `mlx-4bit`），断点续传与 SHA 校验沿用；进度按目标文件磁盘字节数轮询（对 7 GB 级下载足够精确）；可取消（终止子进程，保留已下载分片供续传）。
5. **默认模型设置**：「默认设置」卡片——默认推理引擎（`default_backend`，复用）、默认 MLX 变体（`mlx_variant`，仅列已安装档位）、**默认 LoRA**（新增设置 `default_lora`：无 / 已安装的 LoRA；新建歌曲自动预选，可随时改）。
6. **服务端**：`GET /api/models`（清单 + 状态 + 进度）、`POST /api/models/download`（组件 + 源，排队）、`POST /api/models/cancel`；设置新增 `download_source`、`default_lora`；删除模型不在本次范围（Non-goal）。
7. **非目标**：不做模型删除 UI（占用空间清理仍走文件系统）；不做断点下载的网络层自研（沿用现有下载器）；不改生成/转录主队列；不做 Windows 上的 MLX 组（该组仅 macOS 平台显示）。

## Capabilities

### New Capabilities

- `model-management`: 应用内模型管理契约——组件清单与分组、下载源切换、下载通道与进度、取消与续传、默认模型设置。

### Modified Capabilities

- `web-ui-design`: 冻结基线显式修订——侧栏新增「模型」导航项 + 新增 `#view-models` 页面。

## Impact

- **代码**：`web/server.py`（清单/下载/取消端点 + 独立下载线程 + 设置字段）、`tools/hf_download.py`（细粒度组件模式与 `mlx-bf16`/`mlx-4bit`）、`web/static/app.js`（导航 + 页面渲染 + 下载轮询）、`index.html`（侧栏项与视图容器）、`i18n.js`（约 35 条文案）、`styles.css`（页面样式，复用既有组件模式：`.set-seg`、卡片、进度条）。
- **基线截图**：侧栏新增项出现在**所有页面**——`docs/ui-baseline/{en,zh}/` 现有一套 5 页全部重截，并**新增 `models.png`**（en/zh）——每套 6 张。
- **测试**：服务端清单/下载端点的校验用例（组件名校验、源校验、重复下载拒绝）；`pytest` 全量绿色；浏览器实测下载一个小组件（realaudio 0.17 GB）端到端 + 取消 + 源切换。
- **风险**：真实大模型下载耗时长——实施验证选小体积组件（realaudio/LoRA），大组件逻辑同一路径；hf 直连在本机不通属环境事实（已在使用说明标注，默认走镜像）。
