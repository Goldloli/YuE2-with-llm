# Proposal: llm-multi-provider

## Why

用户对上一版单端点 LLM 配置不满意，要求参考其另一个项目 `xiaoheihe_crawler`（sentiment-monitor）的 LLM 体系，把「LLM 配置」升级为：

1. **多平台模型**——按平台预设管理多个供应商配置（DeepSeek / 通义千问 / 智谱 GLM / Kimi / MiniMax / OpenAI / Ollama / 自定义），切换即用；
2. **一键拉取模型**——从供应商 OpenAI 兼容 `/models` 拉取模型清单，选中即填默认模型（Ollama 回退原生协议）；
3. **工作台式试聊面板**——页面对话区完整参考其工作台版式：**左侧会话记录列表、中部对话区、输入区右下角选择模型**（含供应商与模型弹层、逐字流式、停止保留、会话新建/切换/删除、会话本地持久化）。

参考项目对应实现：`backend/services/llm/{presets,providers,client}.py`、`routers/providers.py`、`api/llm.ts`、`SettingsView.vue` 供应商区块、`components/ai/ConversationList.vue`、`components/workbench/WorkbenchComposer.vue`（右下角模型弹层）、`routers/ai.py`（SSE 流式）与 `theme.css` 的 `.conv-*` / `.workbench-*` 版式。功能与交互语义按其移植，视觉沿用我们已冻结的深色风格（不搬其 Element Plus 皮肤与浅色主题）。

## What Changes

**（视觉变更声明：LLM 配置页重构——供应商列表 + 弹窗表单 + 工作台式试聊面板；实施后重截 `llm.png`）**

1. **多供应商模型**：
   - 预设 8 个：`deepseek / qwen / glm / kimi / minimax / openai / ollama / custom`（含默认 base_url；`ollama` 为本地预设允许 http 回环；`custom` 空）——在参考的 7 个基础上补 OpenAI；
   - 持久化：`web/data/settings.json` 新增 `llm_providers`（数组：id/name/preset/base_url/api_key/default_model/enabled）与 `llm_active_provider`；
   - 校验照参考：base_url 仅 http(s)、禁内嵌凭据/query/fragment、http 仅允许回环；name 非空；preset 枚举；api_key 语义沿用（缺省=保持 / 空串=清除 / 非空=设置）、读取侧仅掩码；
   - **legacy 兼容**：旧单端点字段（`llm_base_url/llm_model/llm_api_key`）保留读取兼容——列表为空且旧字段有值时，读侧合成一个 `legacy` 条目并视为激活；该条目编辑保存后落为正式条目、清空旧字段（不做主动写迁移）；
   - 增强与翻译链改用「激活供应商」（页面级「当前使用」）；未配置/停用时按「LLM 未配置」行为回落（牌堆、词典降级，对外契约不变）。
2. **一键拉取模型**：新端点 `POST /api/llm/models`（无状态探测，表单未保存值即可用；api_key 留空可借已存条目的 key）→ 200 包络 `{ok, items, message, error_code}`；1MB 响应与 500 条上限；错误分类（invalid_url/timeout/connect_failed/auth_failed/rate_limited/http_error/bad_response/too_large）；`ollama` 失败回退 `{base}/api/tags`。前端「拉取模型」→ 候选下拉（仍可手输）；base_url 变化使候选失效、拉取失败不影响手输。
3. **工作台式试聊面板**（参考项目工作台的移植版）：
   - **版式**：面板内两栏——左侧 208px 会话列表（「新建」整宽按钮 + 「最近会话」+ 条目：标题/时间/选中态/hover 删除）；右侧对话区（消息列 max-width 760 居中 + 底部输入卡）；输入卡底栏**右下角为模型选择器**（显示 `供应商 · 模型`，点击向上弹出 280px 弹层：供应商列表 + 模型快捷选项 + 「选择模型」手输 + 「拉取模型」+ 错误提示），右侧为发送/停止按钮；卡片下方一行提示（Enter 发送 · Shift+Enter 换行 · 对话仅存本机）；
   - **消息**：用户消息为右侧气泡（`16px 16px 4px 16px` 圆角、14px），助手消息为无气泡正文（行高 1.8）；流式逐字追加；
   - **会话**：新建 / 切换 / 删除（确认）；标题取首条用户消息前 24 字符（空则「新对话」）；**持久化到 `web/data/llm_chats.json`**（会话 ≤100、每会话消息 ≤500，超出淘汰最旧）；会话记住自己的 `provider_id`/`model`（模型选择器改动即写回），新会话默认取页面级「当前使用」的供应商与默认模型；
   - **流式与停止**：SSE 逐块 `data: {"delta"}`、结束 `[DONE]`；停止（中断流）保留已收内容并落盘；首字节前失败返回 JSON 错误、流中失败发 `error` 事件并保留已收部分。
4. **测试连接**：`/api/llm/test` 增加 `provider_id`（借用已存 key 与 base_url）；列表条目内「测试」按钮。
5. **文档与基线**：`packaging/使用说明.md` LLM 段落更新（多平台 + 拉取模型 + 试聊）；`docs/ui-baseline/{en,zh}/llm.png` 重截（侧栏与其余页面不变）。

非目标（Non-goals）：不做消息编辑/撤回、revision 快照、附件、工具调用与 Agent（参考项目这些能力不搬）；不做跨设备同步（会话存本机 `web/data`）；不做多供应商并发/负载均衡；不改增强与翻译的对外行为契约；不改 `llm_timeout` / `llm_enhance_output` 的全局语义。

## Capabilities

### New Capabilities

- `llm-chat`: 试聊会话存储与管理（`web/data/llm_chats.json`、CRUD、上限与标题）+ 试聊流式轮次（服务端掌握历史、轮次持久化、SSE 事件、错误语义）。

### Modified Capabilities

- `app-settings`: 「LLM 端点配置」重写为多供应商模型（列表 + 激活 + 校验 + 掩码 + legacy 合成与迁移）；新增「LLM 模型拉取」；「LLM 连通性测试」补充 `provider_id` 借用语义。
- `web-ui-design`: 「侧栏「LLM 配置」导航与配置页」修订为 供应商列表 + 试聊面板版式；新增「试聊面板版式」与「试聊对话交互」要求（视觉变更声明与基线重截）。

## Impact

- **后端**：`web/server.py`（providers 校验/CRUD/激活/legacy 合成、`/api/llm/models`、会话 CRUD、`/api/llm/chat` 流式轮次、test 借 key）；`src/yue2/style_localization.py`（`llm_provider()` 解析改为激活条目 + legacy 兼容；流式对话转发助手）。
- **数据**：新增 `web/data/llm_chats.json`（本机会话存储，随 `web/data/` 既有规则不进一键包）。
- **前端**：`web/static/app.js`（LLM 页重构、供应商弹窗表单、试聊面板：会话列表/对话区/模型弹层/流式渲染）、`web/static/i18n.js`（en/zh 新键）、`web/static/styles.css`（试聊面板样式，复用既有令牌与组件语言）。
- **测试**：`tests/test_web_llm.py` 大扩（providers/拉取/会话 CRUD/流式轮次/持久化与上限）；`tests/test_web_settings.py`、`tests/test_style_localization.py` 相关更新。
- **文档/基线**：`packaging/使用说明.md`；`docs/ui-baseline/{en,zh}/llm.png` 重截。
- **风险**：中——settings 结构变化但有 legacy 兼容兜底；SSE 流式 + 中断持久化需处理首字节前后两类失败；LLM 页重写已在视觉变更声明中列出。
