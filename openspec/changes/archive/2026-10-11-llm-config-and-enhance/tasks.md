# Tasks: llm-config-and-enhance

## 1. 后端：配置与连通性

- [x] 1.1 `web/server.py` settings：新增 `llm_base_url/llm_model/llm_api_key/llm_timeout/llm_enhance_output` 校验（URL 形态、超时 1–60、枚举）；读取侧提供非敏感字段与 `llm_api_key_masked`，GET 与 `/api/state` MUST NOT 含明文；key 语义（缺省=保持 / 空串=清除 / 非空=设置）；验证：非法值 422、掩码与清除单测
- [x] 1.2 `POST /api/llm/test`：以请求内候选配置（未提供回落已保存 → 环境变量）发起最小 chat 请求；返回 ok/耗时/可读错误；不落盘；验证：成功与失败两态（mock + 实机 12ms）
- [x] 1.3 配置合并助手（settings > env，供翻译链/增强/测试共用）；`LlmProvider` 超时上限由 10s 放宽至配置值（1–60，默认 10）；验证：优先级单测

## 2. 后端：增强与翻译链

- [x] 2.1 `POST /api/llm/enhance`：词表注入（读 `zh_style_terms.json` 构造「中文（英文）」清单）、zh/en 双模式提示词、输出清洗（去引号/反引号/代码围栏/换行/解释文字 → 逗号分词、去空段、去重、≤200 字符且 ≤12 词条）、未配置 4xx、空 style 422、失败可读错误
- [x] 2.2 翻译链混合策略：词典全覆盖（输出无中文残留）→ 词典且不调 LLM；未全覆盖 → LLM（配置时）；否则词典部分结果；核查并更新既有链序测试
- [x] 2.3 测试：新增 `tests/test_web_llm.py`（mock LLM：enhance 正常/清洗/未配置/失败、test 成功与失败）；`tests/test_style_localization.py` 增加全覆盖跳过 LLM、未覆盖用 LLM、无 LLM 降级；`tests/test_web_settings.py` 增加 LLM 字段与掩码；验证：全量 271 passed

## 3. 前端

- [x] 3.1 侧栏「LLM 配置」（`ph-robot`）+ `#view-llm` 页面：base_url / model / api_key（掩码占位）/ 超时 / 增强输出语言分段控件 / 测试连接 / 保存；toast 反馈；i18n en/zh 齐备
- [x] 3.2 魔法棒改造：已配置 → 增强流程（加载禁用态、结果预览确认、确认替换并触发 input、失败保留原文、空输入提示）；未配置 → 保持牌堆行为不变
- [x] 3.3 实机走查（Playwright）：保存与掩码回显、测试连接、增强 zh/en 成功、失败（不可达端点）、空输入、未配置回落——六态全过 + 配置→链直调验证

## 4. 基线（视觉变更）

- [x] 4.1 `docs/ui-baseline/{en,zh}/` 因侧栏新增项全量重截（14 张）+ 新增 `llm.png`（en/zh）；README 页面清单补 llm 行（顺带补历史遗漏的 models 行）

## 5. 收尾

- [x] 5.1 `packaging/使用说明.md` 常见问题加「LLM 配置」指引（OpenAI 兼容端点示例）
- [x] 5.2 全量 pytest 绿 + `openspec validate llm-config-and-enhance --strict`；归档；`codegraph sync`
