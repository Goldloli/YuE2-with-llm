# model-management Specification

## Purpose
TBD - created by archiving change model-manager. Update Purpose after archive.

## Requirements

### Requirement: 模型清单与状态

系统 MUST 提供模型清单接口（`GET /api/models`），按组返回全部可管理组件：核心模型、解码器、扩展工具、逐个 LoRA、音频转录、MLX 变体（8-bit / bf16 / 4-bit，仅 macOS 平台展示）。每组件的条目 MUST 包含：标识、显示名、体积、目标路径集合、下载模式、平台限制、必备标志；状态 MUST 实时计算（全部目标文件就位=已安装；下载中返回已落盘字节与总量）。

#### Scenario: 清单反映安装状态

WHEN 已安装核心模型并打开模型页
THEN 核心组件显示「已安装」，未安装组件显示「未安装」与体积

#### Scenario: 平台过滤

WHEN 在非 macOS 平台打开模型页
THEN MLX 组不出现；其余组正常

### Requirement: 下载源切换

下载源 MUST 支持「国内镜像（hf-mirror.com）」与「国际直连（huggingface.co）」两种，以设置 `download_source` 持久化（缺省 mirror）。每次下载 MUST 使用发起时刻的当前选择；下载进行中切换 MUST 对后续任务生效且 MUST NOT 中断当前任务。

#### Scenario: 发起时选源

WHEN 用户在页面把下载源切到「国际直连」后发起某组件下载
THEN 该下载经 huggingface.co 进行；切回镜像后下一次下载经 hf-mirror.com

### Requirement: 下载通道与进度

下载 MUST 在独立通道执行（单并发），与生成/转录任务并行且 MUST NOT 阻塞主任务队列。下载 MUST 复用既有下载器的断点续传与校验能力；进度 MUST 以目标路径已落盘字节与组件总体积计算并可通过清单接口轮询。同一组件已有下载进行中时，再次发起 MUST 被拒绝（409）。

#### Scenario: 并行不阻塞

WHEN 一个 7 GB 组件正在下载
THEN 用户仍可创建/播放歌曲，生成任务正常执行

#### Scenario: 重复发起

WHEN 对同一组件在下载中再次发起下载
THEN 返回 409，不产生第二个下载进程

### Requirement: 取消与续传

下载 MUST 可取消：取消终止下载进程并保留已落盘的分片；对未完成组件再次发起下载时 MUST 从已有分片续传（不从头开始）。取消后组件状态回到「未安装（部分已下载）」。

#### Scenario: 取消后重启下载

WHEN 用户取消一个未完成的下载，随后重新发起
THEN 新下载从断点继续，最终校验通过后组件转为「已安装」

### Requirement: 默认模型设置

模型页 MUST 提供默认模型设置：默认推理引擎（复用 `default_backend`）、默认 MLX 变体（复用 `mlx_variant`，仅列已安装档位）、默认 LoRA（新增 `default_lora`，取值无或已安装 LoRA 标识）。`default_lora` MUST 在新会话的创作面板预选（MLX 引擎下不预选，因 MLX 不支持 LoRA），用户可当场更改。

#### Scenario: 预设默认 LoRA

WHEN 用户把默认 LoRA 设为 Instrumental v3 后刷新页面
THEN 创作面板的 LoRA 选择预选该适配器；切换引擎为 MLX 时预选清空

### Requirement: 默认模型设置控件即时反馈

模型页「默认设置」卡中的控件（默认推理引擎、默认 MLX 变体、默认 LoRA）MUST 在点击后即时反映到界面：活动态 MUST 渲染自所保存的设置值（而非会话瞬时状态），任何轮询跳过重建的判定 MUST 将该值纳入变化检测。默认推理引擎的切换 MUST 同步当前会话引擎（创作面板 pill 随动；切至 MLX 且已选 LoRA 时按既有规则清空并提示）。设置弹窗中的同名字段 MUST 具有相同行为。

#### Scenario: 模型页切换默认引擎

WHEN 用户在模型页把默认引擎从 MLX 切到 PyTorch
THEN 活动态立即迁移到 PyTorch、创作面板 pill 同步为 PyTorch、刷新页面后设置保持

#### Scenario: 无反馈不得发生

WHEN 用户点击任一默认设置控件
THEN 界面 MUST 产生与服务器状态一致的可见变化（活动态迁移或既有提示），不得出现「点击无反应」
