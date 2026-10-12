# Design: settings-menu-overhaul

## 分组布局

设置弹窗自上而下分六组，组间以现有 `--line-soft` 细分隔 + 12px 小标题（13px、--text-3、字重 600）区隔；行控件沿用 `.set-row` / `.set-seg` / `.set-input` / `.set-note`，不引入新组件：

| 分组 | 行 |
|---|---|
| 创作默认 | 默认推理后端 · 默认模式 · 默认时长上限 · 默认 CFG · 风格提示词语言 |
| 生成行为 | 自动播放 · 桌面通知 · 刷新间隔 |
| 模型与性能 | 音频解码器 · MLX 量化变体 · 推理后端(CUDA) · FP8/AR(CUDA) · 显存预算 · 环境自检 |
| 界面 | 界面语言 · 启动页面 · 默认排序 · 减少动效 |
| 高级与维护 | 存储占用 + 清理 · 重置设置 |
| 状态 | 模型 · 设备 · 音频转录（只读行，保留现有） |

## 关键决策

### 决策 1：`default_backend` 的默认值 = mlx，但按可用性回退

用户点名「默认使用 MLX」。实现：
- 服务端 `settings.default_backend` 缺省为 `"mlx"`；
- 前端启动时若 `/api/state.mlx_available === false`，忽略该默认并回退 `torch`（选择器仍显示实际可用的）；
- 服务端 `queue_song` 的 `backend` 参数默认值由硬编码 `"torch"` 改为读取设置，非法/不可用回退 torch。
- 老用户影响：settings.json 无该键 → 读为 mlx（推荐值），行为变化属「预期默认」而非静默变更——写入 proposal 已声明。

### 决策 1b：变体行的建议文案（含实测数据）

设置行的附注文案建议：「8-bit：近 bf16 质量、速度最佳（20 秒歌曲实测约 17s，比 bf16 快约 1.7×，比 PyTorch 快约 3.6×）；bf16：全精度、约慢 70%（约 28s）」。数据来自本机两轮基准（同 prompt/seed/500 tokens），写入 `tools/download_mlx.sh` 头部注释留档（仓库无独立 models 文档，MLX 说明一直集中在该脚本）。

### 决策 2：「默认值」的语义边界

`default_mode` / `default_max_seconds` / `default_cfg` / `default_sort` 只作用于**初始值与重置表单**（应用启动、创作面板重置、clear-form）。用户当场改动不回写设置（避免「改一次变成永久」的意外）。`start_view` 同理只作用于应用启动。

### 决策 3：即时生效 vs 下次任务生效

| 设置 | 生效时机 |
|---|---|
| default_*（创作默认） | 下一次打开/重置面板 |
| 自动播放/通知 | 立即（事件监听读当前值） |
| 刷新间隔 | 立即（清掉旧 interval 重建） |
| 减少动效 | 立即（body class） |
| start_view / default_sort | 下次启动 |
| mlx_variant | 下个 MLX 任务（子进程启动时读取） |
| 解码器/后端/预算等（现有） | 现有语义不变；decoder 新增 merge 档：下个 PyTorch 生成/重混解码 |

### 决策 7b：decoder 三档的解析与校验

- 三档权重目录：`models/YuE2-Vae`（default）、`models/YuE2-Vae-legacy`（legacy）、`models/YuE2-Vae-merge`（merge，下载自 `Mothersuperior/YuE2-Vae-merge-0.666` 的 torch safetensors）；
- 服务端校验：`decoder∈{default,legacy,merge}`，所选档位目录缺 `model.safetensors` 时 422（附下载提示命令）；
- 生成与重混解码（`_generate` / `_redecode`）的 vae 路径按档位解析；MLX 不受影响；
- UI：现有两档分段控件扩为三段；缺档位置灰 + tooltip 提示 `tools/download_extras.sh`。

### 决策 4：桌面通知的实现约束

- 仅用于「任务完成」一类事件，点击通知不承诺聚焦细节（浏览器限制）；
- 首次把开关拨到「开」时请求 `Notification.requestPermission()`；被拒绝则开关回弹并 toast 说明；
- 后端无 Notification 时（非 https/localhost 场景本应用不涉及）静默跳过。

### 决策 5：减少动效的实现

`body.no-motion` 下统一 `transition-duration: 0.01ms !important; animation-duration: 0.01ms !important`（保留 `animation-fill-mode` 语义，避免 `display:none` 类破坏性覆盖）；抽屉滑动与 toast 变即时。默认关，不影响现有基线视觉。

### 决策 6：存储统计与清理

- 统计：`GET /api/storage` 用 `os.scandir` 递归求和 outputs / uploads 总大小、`latent.npy` 合计、文件数；毫秒级，不缓存。
- 清理：`POST /api/storage/cleanup` 删除所有 `outputs/*/latent.npy`，返回释放字节数；前端二次确认（确认文案明确「删除后无法对旧歌重新解码/重混解码」）。
- 不删音频、谱面、request/result 等交付物。

### 决策 7：字段与校验（服务端）

`SettingsUpdate` 新增：`default_backend∈{torch,mlx}`、`default_mode∈{simple,advanced}`、`default_max_seconds∈[5,360]∨null`、`default_cfg∈[0,20]∨null`、`autoplay_on_complete:bool`、`notify_on_complete:bool`、`poll_interval∈{1.5,3,5,10}`、`mlx_variant∈已安装变体集合`（服务端扫 `models/YuE2-3B-MLX/*/model.safetensors` 得集合，当前={bf16, 8bit}（bf16 已本机转换）；4bit 经 `convert.py` 转换或下载后自动入集合）、`start_view∈{create,library}`、`default_sort∈{new,old,title}`、`reduce_motion:bool`、`style_language∈{auto,en,off}`（已存在于 SettingsUpdate）。非法值 422，与现有风格一致。

## 风险与缓解

- **默认 MLX 的行为面**：MLX 未安装/未下载时回退 torch（决策 1）；批量创建继承同一默认。
- **i18n 量**：约 30 条新 key，en/zh 同批维护。
- **设置弹窗变长**：分组后纵向变长，弹窗维持现有最大高度与内部滚动；若超长在实施时确认滚动体验。
