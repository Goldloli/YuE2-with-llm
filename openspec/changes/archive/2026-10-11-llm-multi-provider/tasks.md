# Tasks: llm-multi-provider

## 1. 后端：多供应商模型

- [x] 1.1 预设表（8 个：deepseek/qwen/glm/kimi/minimax/openai/ollama/custom，含默认 base_url 与本地标记）+ `validate_base_url`（仅 http(s)、禁凭据/query/fragment、http 仅回环）+ 掩码沿用现状；验证：单测
- [x] 1.2 settings：`llm_providers`（id 服务端生成、name/preset/base_url/api_key/default_model/enabled 校验）与 `llm_active_provider` 的 CRUD 语义（api_key 缺省=保持 / 空串=清除；删除激活条目置空）；验证：非法值 422、掩码、清除、删激活
- [x] 1.3 legacy 兼容：列表为空且旧字段有值时读侧合成 `legacy` 条目并视为激活；编辑保存后落为正式条目并清空旧字段；删除即清空旧字段；验证：三种迁移路径单测
- [x] 1.4 `/api/state` 与 `GET /api/settings` 下发供应商列表（含掩码）与激活项
- [x] 1.5 `POST /api/llm/models`：无状态探测（候选值 + `provider_id` 借 key）、`{base}/models` 解析（去重排序、≤500、≤1MB）、ollama 回退 `/api/tags`、错误分类包络；验证：mock 成功/401/超时/ollama 回退/超限
- [x] 1.6 `POST /api/llm/test` 增加 `provider_id` 借用；增强/翻译链解析改为激活条目（+ legacy 兼容），`llm_provider()` 单测更新
- [x] 1.7 增强与翻译回归：激活供应商缺省/停用时回落行为不变（牌堆、词典降级）

## 2. 后端：试聊会话与流式轮次

- [x] 2.1 会话存储模块：`web/data/llm_chats.json`（原子写）、结构 `{id,title,created_at,updated_at,provider_id,model,messages[]}`、上限（会话 ≤100 淘汰最旧、每会话消息 ≤500）、标题自动取首条用户消息前 24 字（空「新对话」）；验证：单测（并发写、上限淘汰、标题）
- [x] 2.2 会话 CRUD 端点：`GET /api/llm/conversations`（不含消息、按更新时间倒序）/ `POST`（新建空会话）/ `GET /{id}`（含消息）/ `PUT /{id}`（title/provider_id/model）/ `DELETE`；验证：404/非法值
- [x] 2.3 `POST /api/llm/chat` 轮次：`{conversation_id,text,provider_id?,model?}` → 校验（404/空文本 422/供应商解析 409）→ 服务端取历史（最近 12 条且 ≤8000 字符）→ 先落用户消息与 meta（标题/模型）→ `stream:true` 上游转发 → `data:{"delta"}`/`[DONE]` → 结束或中断时落已收内容的 assistant 消息；总时长 ≤120s
  - 实机发现：Starlette 0.50 在客户端断连时**从不关闭**同步迭代器（`iterate_in_threadpool` 无 finally），finally 落盘必然不可靠 → 改为**增量落盘**（首个 delta 即建消息，之后 0.2s 节流更新；断连时已收内容必然在盘上）
- [x] 2.4 验证：mock 流式成功、未配置 409、上游 401 首字节前 502、中途断流保留已收、停止落盘部分回复、历史截断、上限淘汰（+「不关闭迭代器」的放弃路径单测）

## 3. 前端

- [x] 3.1 LLM 页重构（上：偏好区「当前使用」+ 增强输出语言 + 超时；中：供应商列表 `.mdl-row` 行 + [测试][编辑][删除] + 「新建」）
- [x] 3.2 弹窗表单（`#modal`）：名称 / 预设下拉（切换自动填名称与 base_url，手改名不覆盖——实机发现读表单旧值的 bug 并修复）/ 接口地址 / API Key（掩码占位 + 清除）/「拉取模型」+ 候选下拉（可手输，base_url 变化清空）/ 启用；保存就地报错
- [x] 3.3 试聊面板（下）：两栏（左 208px 会话列表：新建/最近会话/标题/时间/选中/hover 删除；右对话区：消息 760 居中 + 输入卡）
- [x] 3.4 输入卡：textarea（60–180px 自增高）+ 底栏右下角**模型选择器**（`供应商 · 模型` 省略显示，向上弹层：供应商/模型快捷选项/「选择模型」手输/「拉取模型」/错误）+ 发送/停止按钮 + 提示行
- [x] 3.5 交互：流式逐字、停止保留已收、Enter 发送 / Shift+Enter 换行（IME 保护）、新建/切换/删除会话（确认）、模型改动写回会话（PUT）、错误态保留已收、空会话空态
  - 实机发现并修复：`renderLlmPage` 重建骨架后未重填聊天区（保存后面板消失）、弹层选项点击因重渲染被全局监听误判为「点击外部」而关闭、用户消息未入 `chatData.messages`（收尾重渲染后消失）、`#view-llm` 缺 flex 容器样式导致页内不能滚动（试聊面板底部不可达）
- [x] 3.6 i18n en/zh：全部新键（预设名、按钮、错误、试聊文案、键盘提示）

## 4. 测试

- [x] 4.1 `tests/test_web_llm.py` 扩展：providers CRUD/校验/掩码/激活/legacy、`/api/llm/models` 全错误分类、会话 CRUD、chat 轮次全路径（含持久化断言）
- [x] 4.2 `tests/test_web_settings.py` / `tests/test_style_localization.py` 适配（激活解析、legacy 兼容）
- [x] 4.3 全量 pytest 全绿（294 passed, 12 skipped）

## 5. 实机走查与基线

- [x] 5.1 Playwright 走查（mock 上游）：预设切换自动填、拉取模型、保存并测试（2ms）、新建会话与自动标题、发消息流式、停止（落盘部分回复）、切换/删除会话、模型弹层选择与应用、当前使用切换、清理演示数据
- [x] 5.2 `docs/ui-baseline/{en,zh}/llm.png` 重截（新页式，页内下滚一屏取景）；README 行更新；`packaging/使用说明.md` LLM 段落更新

## 6. 收尾

- [x] 6.1 `openspec validate llm-multi-provider --strict`；归档；`codegraph sync`；缓存清理
