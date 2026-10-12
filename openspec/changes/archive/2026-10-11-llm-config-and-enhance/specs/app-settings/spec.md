# Spec Delta: app-settings（新增）

## ADDED Requirements

### Requirement: LLM 端点配置

系统 MUST 支持在 Web 端配置风格翻译与增强所用的 LLM 端点（OpenAI 兼容 `chat/completions`）：`llm_base_url`（空串=未配置；非空 MUST 为 http/https URL）、`llm_model`（空串=未配置）、`llm_api_key`（可选）、`llm_timeout∈[1,60]` 秒（缺省 10）、`llm_enhance_output∈{zh,en}`（缺省 `zh`）。非法值 MUST 返回 422。配置 MUST 持久化于 `web/data/settings.json`；api_key 明文存储（本地应用约定，该目录不随一键包分发），且 MUST NOT 出现在任何读取响应的明文位置——`GET /api/settings` 与 `GET /api/state` MUST 以 `llm_api_key_masked`（至多含尾部 4 位；未设置时为空）表示是否已配置。`POST /api/settings` 对 `llm_api_key` 的语义：字段缺省=保持、空串=清除、非空=设置。生效优先级：设置 > 环境变量（`YUE2_STYLE_LLM_*`）> 未配置。

#### Scenario: 保存与掩码回显

WHEN 保存 base_url / model / api_key 后重新读取配置
THEN 返回不含 api_key 明文、仅有掩码，其余字段为已保存值

#### Scenario: 不提交 key 字段保持不变

WHEN 再次保存其他字段且请求未包含 `llm_api_key`
THEN 已保存的 key 保持不变

#### Scenario: 清除 key

WHEN 提交 `llm_api_key: ""`
THEN 已保存 key 被清除，掩码为空

#### Scenario: 非法值拒绝

WHEN 提交 `llm_timeout: 0`、`llm_timeout: 61`、`llm_enhance_output: "fr"` 或 `llm_base_url: "ftp://x"`
THEN 返回 422，设置不变

#### Scenario: 优先级

WHEN 设置中已配置端点且环境中也存在 `YUE2_STYLE_LLM_*`
THEN 翻译与增强 MUST 使用设置中的端点

### Requirement: LLM 连通性测试

`POST /api/llm/test` MUST 以请求内候选配置（未提供的字段回落已保存配置，再回落环境变量）发起一次最小 `chat/completions` 请求，返回成功/失败、耗时与可读错误摘要；测试 MUST NOT 修改任何已保存配置，失败 MUST NOT 影响后续流程。

#### Scenario: 测试成功

WHEN 以有效端点发起测试
THEN 返回成功与耗时

#### Scenario: 测试失败不落盘

WHEN 以不可达端点发起测试并失败
THEN 返回可读错误摘要，已保存配置保持不变
