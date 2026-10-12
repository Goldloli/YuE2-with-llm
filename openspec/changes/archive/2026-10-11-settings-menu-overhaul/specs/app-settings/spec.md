# Spec Delta: app-settings（新能力）

## ADDED Requirements

### Requirement: 偏好持久化与校验

`POST /api/settings` MUST 持久化客户端偏好并逐字段校验：`default_backend∈{torch,mlx}`、`default_mode∈{simple,advanced}`、`default_max_seconds∈[5,360]∨null`、`default_cfg∈[0,20]∨null`、`autoplay_on_complete:bool`、`notify_on_complete:bool`、`poll_interval∈{1.5,3,5,10}`、`mlx_variant∈已安装变体集合`（服务端扫描 `models/YuE2-3B-MLX/*/model.safetensors` 动态得出）、`start_view∈{create,library}`、`default_sort∈{new,old,title}`、`reduce_motion:bool`、`style_language∈{auto,en,off}`。非法值 MUST 返回 422。缺省值 MUST 在读取时合并：`default_backend` 缺省为 `mlx`，其余新字段缺省为「现状行为等价」。

#### Scenario: 非法值拒绝

WHEN 提交 `default_backend: "cuda"` 或 `mlx_variant: "2bit"`
THEN 服务端返回 422，设置不变

#### Scenario: 默认后端回退

WHEN `default_backend=mlx` 但本机 `mlx_available()` 为假
THEN 创建任务回退 PyTorch，界面选择器显示实际可用后端

### Requirement: 默认值仅作用于初始状态

`default_mode` / `default_max_seconds` / `default_cfg` / `default_sort` / `start_view` MUST 仅作用于应用启动与创作面板重置（clear-form）时的初始值；用户当场修改 MUST NOT 回写设置。

#### Scenario: 当场修改不回写

WHEN 用户在创作面板把时长从默认 60 改为 30 并生成
THEN 设置中的 `default_max_seconds` 保持 60 不变，下次重置表单仍预填 60

### Requirement: 生成行为偏好

`autoplay_on_complete` 开启时，任务从进行中迁移到完成 MUST 自动开始播放该歌曲；`notify_on_complete` 开启时 MUST 以浏览器 Notification 通知（首次开启时请求权限，被拒绝时开关回弹并提示）；`poll_interval` MUST 控制列表刷新定时器的间隔并在修改后立即重建定时器。

#### Scenario: 完成自动播放

WHEN 设置开启自动播放且一首生成中的歌变为完成
THEN 播放器自动开始播放该歌曲

#### Scenario: 通知权限被拒

WHEN 用户开启桌面通知但浏览器拒绝权限
THEN 开关回弹为关，toast 提示权限被拒

### Requirement: 减少动效

`reduce_motion` 开启时，界面 MUST 禁用过渡与动画（抽屉滑动、toast 入场、旋转等待等变为即时呈现），且 MUST NOT 改变任何静态视觉样式。

#### Scenario: 抽屉即时开合

WHEN 减少动效开启时打开详情面板
THEN 面板无滑动过渡直接呈现

### Requirement: 存储统计与清理

`GET /api/storage` MUST 返回 outputs / uploads 占用、`latent.npy` 合计与文件数；`POST /api/storage/cleanup` MUST 删除全部输出目录中的 `latent.npy` 并返回释放字节数，MUST NOT 删除音频、谱面、request/result 等交付物。

#### Scenario: 清理中间文件

WHEN 用户确认清理中间文件
THEN 各输出目录的 `latent.npy` 被删除，占用统计相应下降，歌曲的音频与谱面不受影响

### Requirement: 设置重置

设置 MUST 提供重置为出厂默认的能力，执行前需要二次确认；重置后 MUST 立即刷新设置界面与受影响的客户端状态。

#### Scenario: 重置设置

WHEN 用户确认重置设置
THEN 所有偏好恢复出厂默认，弹窗内容立即反映，后续行为按默认值执行

### Requirement: 音频解码器三档

`decoder` MUST 支持 `default` / `legacy` / `merge` 三档；对应权重目录缺失时 MUST 返回 422 并提示下载命令。解码器档位 MUST 仅影响 PyTorch 生成与重混解码路径，MLX 生成 MUST 保持使用变体自带解码器。

#### Scenario: 未下载的 merge 档

WHEN merge 权重未安装且提交 `decoder: "merge"`
THEN 返回 422，消息含 `tools/download_extras.sh` 提示

#### Scenario: 三档生成

WHEN 用户选择 merge 档并生成
THEN 使用 `models/YuE2-Vae-merge` 权重解码；重混解码（redecode）同档生效

### Requirement: MLX 变体展示

前端 MUST 展示当前激活的 MLX 变体：创作面板模型下拉的 MLX 选项标签 MUST 动态反映激活档位（如 `MLX · bf16` / `MLX · 8-bit`，不再写死 8-bit）；详情面板技术信息的引擎行对 MLX 歌曲 MUST 显示其生成时的实际变体（读 `result.json.backend` 的 `mlx-<variant>`），无该字段的存量歌曲回退显示 8-bit。设置中切换变体后，同日志的展示 MUST 同步刷新。`/api/state` MUST 下发 `mlx_variant`（当前档位）与已安装变体集合。

#### Scenario: 切换变体后展示同步

WHEN 在设置中把变体从 8-bit 切到 bf16
THEN 创作面板模型下拉的 MLX 标签显示 bf16；此后生成的 MLX 歌曲在详情引擎行显示 MLX · bf16

#### Scenario: 存量歌曲回退

WHEN 查看切换前生成的 MLX 歌曲（result.json 无变体字段）
THEN 引擎行显示 MLX · 8-bit，不报错
