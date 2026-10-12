# Spec Delta: llm-chat（新增能力）

## ADDED Requirements

### Requirement: 试聊会话存储与管理

试聊会话 MUST 持久化于本机 `web/data/llm_chats.json`（MUST NOT 写入 settings 或歌曲数据）。存储结构 MUST 为 `{"conversations": [{id, title, created_at, updated_at, provider_id, model, messages: [{role, content, ts}]}]}`；写入 MUST 原子（临时文件 + 替换），并发调用 MUST NOT 损坏文件。服务端 MUST 提供：`GET /api/llm/conversations`（列表，不含 messages，按 `updated_at` 倒序）、`POST /api/llm/conversations`（新建空会话）、`GET /api/llm/conversations/{id}`（含 messages）、`PUT /api/llm/conversations/{id}`（`title` / `provider_id` / `model`）、`DELETE /api/llm/conversations/{id}`；不存在的 id MUST 返回 404。标题 MUST 自动取首条用户消息的单行前 24 字符（无消息时为「新对话」；显式改名 MUST 保留）。上限：会话 MUST ≤100（超出淘汰 `updated_at` 最旧），每会话消息 MUST ≤500（超出丢弃最旧）。

#### Scenario: 新建与首轮

WHEN 新建空会话并发送首条消息
THEN 列表以其标题与更新时间返回；详情含该条用户消息与回复

#### Scenario: 排序与淘汰

WHEN 会话数超过 100 或单会话消息超过 500
THEN 最旧会话 / 最旧消息被淘汰，其余保持不变

#### Scenario: 更新与删除

WHEN PUT 修改 title/provider/model 或 DELETE 删除
THEN 变更即时持久化；删除不存在的会话返回 404

#### Scenario: 不污染其他数据

WHEN 任意试聊操作完成
THEN `settings.json` 与歌曲数据无任何变化

### Requirement: 试聊流式轮次

`POST /api/llm/chat` MUST 接受 `{conversation_id, text, provider_id?, model?}`：会话不存在 MUST 404；`text` 为空或超 4000 字符 MUST 422；供应商按 请求体 → 会话记录 → 激活供应商 顺序解析，未解析到（未配置或已停用）MUST 409 且 MUST NOT 发起上游调用。服务端 MUST 以会话历史（最近 12 条、总字符 ≤8000，不含本条）加本条组成上下文，先持久化用户消息与 meta（标题 / 供应商 / 模型 / `updated_at`），再以上游 `stream:true` 转发：响应 MUST 为 `text/event-stream`，逐块 `data: {"delta": "<增量>"}`，正常结束 `data: [DONE]`。首个字节前失败 MUST 以 JSON 错误响应（409/502 + 可读 detail）；流中途失败或客户端中断（停止）MUST 保留已生成内容并作为 assistant 消息持久化（空内容则跳过），中断 MUST NOT 影响后续轮次。总时长 MUST ≤120 秒；`max_tokens` / `temperature` 使用服务端固定值；MUST NOT 将消息正文写入日志。

#### Scenario: 流式成功

WHEN 会话可用且上游按块返回内容
THEN 客户端依次收到多个 `delta` 事件与终止 `[DONE]`，用户与助手消息均已持久化

#### Scenario: 未配置

WHEN 会话无 provider 且无激活供应商时调用
THEN 返回 409 JSON 可读错误，不发起上游调用、不落库

#### Scenario: 首字节前鉴权失败

WHEN 上游返回 401/403
THEN 返回 502 JSON 可读错误（不产生半截事件流）

#### Scenario: 停止保留部分回复

WHEN 流式输出中途客户端中断
THEN 已生成内容被持久化为 assistant 消息，刷新后可见

#### Scenario: 流中途失败

WHEN 上游在部分输出后断开
THEN 服务端发送 `data: {"error": ...}` 后结束，已收内容保留

#### Scenario: 历史截断

WHEN 会话累计历史超过 12 条或 8000 字符
THEN 仅最近部分进入上下文，响应不受影响

#### Scenario: 会话不存在

WHEN `conversation_id` 指向已删除的会话
THEN 返回 404，不产生任何持久化变更
