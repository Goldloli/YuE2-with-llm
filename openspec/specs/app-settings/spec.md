# app-settings Specification

## Purpose
TBD - created by archiving change settings-menu-overhaul. Update Purpose after archive.

## Requirements

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

### Requirement: LLM 端点配置

系统 MUST 以**供应商列表**管理 LLM 端点，持久化于 `web/data/settings.json` 的 `llm_providers`（数组）与 `llm_active_provider`（条目 id 或 null）。每个条目 MUST 含：`id`（服务端生成，唯一且稳定）、`name`（非空）、`preset∈{deepseek,qwen,glm,kimi,minimax,openai,ollama,custom}`、`base_url`、`api_key`、`default_model`（允许空）、`enabled`（bool）。系统 MUST 提供预设表（名称 + 默认 base_url；`ollama` 为本地预设、允许 http 回环；`custom` 空 base_url）。校验：`base_url` 仅 http/https、MUST NOT 内嵌凭据/query/fragment、`http` 仅允许回环地址（localhost/127.x），非法值 MUST 返回 422。`api_key` 语义：字段缺省=保持、空串=清除、非空=设置；任何读取响应 MUST NOT 回显明文，MUST 以掩码表示。`llm_active_provider` MUST 指向存在的条目（删除激活条目时置 null）；仅激活且 `enabled` 的条目供风格增强与翻译链使用（`llm_timeout`、`llm_enhance_output` 维持全局）。**legacy 兼容**：当列表为空且旧单端点字段（`llm_base_url`/`llm_model`/`llm_api_key`）有值时，读取侧 MUST 合成一个 `legacy` 条目（preset=custom）并视为激活；该条目被编辑保存后 MUST 落为正式条目并清空旧字段，被删除即清空旧字段。生效优先级（激活条目 > 环境变量 `YUE2_STYLE_LLM_*` > 未配置）保持不变。

#### Scenario: 保存与掩码回显

WHEN 新建一个 DeepSeek 供应商（含 api_key）并设为当前使用
THEN 读取返回供应商列表与激活项，api_key 仅为掩码、不含明文

#### Scenario: 不提交 key 字段保持不变

WHEN 更新其他字段且请求未包含 `api_key`
THEN 该条目已保存的 key 保持不变

#### Scenario: 清除 key

WHEN 提交该条目 `api_key: ""`
THEN 已保存 key 被清除，掩码为空

#### Scenario: 非法值拒绝

WHEN 提交 `preset: "unknown"`、空 name、或 `base_url` 为 `ftp://x` / 含内嵌凭据 / 远程 `http://`
THEN 返回 422，设置不变

#### Scenario: 优先级

WHEN 激活供应商已配置且环境中也存在 `YUE2_STYLE_LLM_*`
THEN 翻译与增强 MUST 使用激活供应商

#### Scenario: legacy 合成与迁移

WHEN 列表为空且旧字段 `llm_base_url`/`llm_model` 有值
THEN 读取侧返回一个 `legacy` 条目且为激活；编辑保存该条目后，旧字段被清空且其成为正式条目

#### Scenario: 删除激活条目

WHEN 删除当前激活供应商
THEN `llm_active_provider` 置 null，增强与翻译回落「LLM 未配置」行为（牌堆/词典），不报错

### Requirement: LLM 连通性测试

`POST /api/llm/test` MUST 以请求内候选配置（未提供的字段回落 `provider_id` 指定条目的已存值，再回落激活条目与环境变量）发起一次最小 `chat/completions` 请求，返回成功/失败、耗时与可读错误摘要；测试 MUST NOT 修改任何已保存配置，失败 MUST NOT 影响后续流程。

#### Scenario: 测试成功

WHEN 以有效端点发起测试
THEN 返回成功与耗时

#### Scenario: 测试失败不落盘

WHEN 以不可达端点发起测试并失败
THEN 返回可读错误摘要，已保存配置保持不变

#### Scenario: 借用已存 key

WHEN 请求携带 `provider_id` 且未提供 `api_key`
THEN 使用该条目已保存的 key 发起测试，key 不出现在任何响应中

### Requirement: LLM 模型拉取

`POST /api/llm/models` MUST 以请求内候选值（`preset`/`base_url`/`api_key`；`api_key` 缺省且给出 `provider_id` 时借用其已存 key；`preset` 需要 key 而缺 key MUST 返回 `auth_failed`）对 `{base_url}/models` 发起**无状态**探测（MUST NOT 落库）。成功 MUST 返回 `{"ok": true, "items": [...], "message": ...}`：items 去重排序、MUST ≤500 条，响应体 MUST ≤1MB（超限报错）。失败 MUST 以 200 包络返回 `{"ok": false, "items": [], "message": <可读中文>, "error_code": ...}`，`error_code∈{invalid_url, timeout, connect_failed, auth_failed, rate_limited, http_error, bad_response, too_large}`。`preset=ollama` 且 OpenAI 兼容探测失败时 MUST 回退 `{base_url 去尾部 /v1}/api/tags` 并解析 `models[].name`。探测失败 MUST NOT 影响任何已保存配置，MUST NOT 阻止用户手输模型名。

#### Scenario: 成功拉取

WHEN 探测一个返回 3 个模型的 OpenAI 兼容端点
THEN 返回 `ok:true`、items 排序去重、message 含数量

#### Scenario: 鉴权失败

WHEN 探测返回 401 且未提供有效 key
THEN 返回 `error_code: auth_failed` 与中文提示，不落库

#### Scenario: ollama 回退

WHEN `preset=ollama` 且 `/models` 探测失败、`/api/tags` 可用
THEN 返回原生协议解析出的模型列表

#### Scenario: 上限与体积

WHEN 响应体超过 1MB 或模型数超过 500
THEN 分别返回 `too_large` 或截断为 500 条且 `ok:true`
