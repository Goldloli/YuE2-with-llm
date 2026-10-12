# Spec Delta: app-settings（修订）

## MODIFIED Requirements

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

## ADDED Requirements

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
