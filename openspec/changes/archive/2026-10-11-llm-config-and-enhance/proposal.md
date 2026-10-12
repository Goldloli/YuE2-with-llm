# Proposal: llm-config-and-enhance

## Why

三个现状叠加出的缺口：

1. 魔法棒目前只会填入预置示例组（`STYLE_SUGGESTIONS`），接不住「黑人说唱」这类词表之外的自由描述；
2. 内置 LLM 基建（`LlmProvider`，OpenAI 兼容端点）已存在于翻译链，但只能靠环境变量配置，普通用户无法启用——`settings-menu-overhaul` 曾把「LLM 端点配置化」列为 Non-goal（涉及密钥存储与连通性测试，另案评估），本案即该评估的落点；
3. 词表文档（298 条）刚落地，正好作为增强的受控词表。

用户确认：侧栏新增「LLM 配置」菜单；魔法棒改为 LLM 增强；**增强输出语言（中文词表 / English tags）在配置页可选**；其余按评审建议执行。

## What Changes

**（视觉变更声明：侧栏新增「LLM 配置」导航项、主区新增配置页、魔法棒交互扩展——按 `web-ui-design` 要求声明，实施后更新基线截图）**

1. **LLM 配置页（新）**：侧栏「模型」之后新增「LLM 配置」→ `#view-llm`。字段：base_url、model、api_key、超时（1–60 秒，默认 10）、**增强输出语言（中文词表 / English tags，默认中文）**；「测试连接」「保存」；复用既有设置组件模式（`.set-input` / `.set-seg` / pill 按钮）。存储 `web/data/settings.json`；api_key 明文存储（本地应用）但**不回显**（读取侧仅掩码）；`web/data` 已在打包排除清单中，密钥不随一键包分发。生效优先级：**设置 > 环境变量**（`YUE2_STYLE_LLM_*`）。
2. **魔法棒 → LLM 增强**：已配置 LLM 时，点击读取风格框文本 → 调 `POST /api/llm/enhance`（词表注入 + 输出清洗）→ 结果经既有 `confirmDialog` 预览确认 → 确认替换 / 取消保留原文；请求期按钮加载禁用；失败保留原文 + toast；空输入提示且不发起请求。**未配置 LLM 时保持现有牌堆行为不变**（优雅降级）。
3. **新端点**：`POST /api/llm/enhance`（zh/en 双模式；未配置 4xx；空输入 422；失败可读错误）与 `POST /api/llm/test`（候选配置连通性测试，不落盘）。
4. **翻译链修订（混合策略）**：词典全覆盖（输出无中文残留）→ 词典（确定性、不调 LLM）；未全覆盖且配置了 LLM → LLM；否则词典部分结果（现状）。增强后的风格框全是词表词 → 生成时零 LLM 开销、输出确定。
5. **视觉基线**：因侧栏新增项，`docs/ui-baseline/{en,zh}/` 全页面重截 + 新增 `llm.png`（en/zh 各一张）；README 页面清单同步。
6. **文档**：`packaging/使用说明.md` 常见问题加「LLM 配置」指引。

非目标（Non-goals）：不做多端点预设管理（单端点）；不做流式输出；简单模式不加增强入口；不改词表内容；不做 LLM 生成歌词/标题等其他 LLM 场景。

## Capabilities

### New Capabilities

- `style-enhancement`: LLM 风格增强端点契约——词表注入、输出清洗与上限、zh/en 输出模式、未配置拒绝、失败不破坏状态。

### Modified Capabilities

- `app-settings`: 新增「LLM 端点配置」与「LLM 连通性测试」要求——字段校验、api_key 掩码与设置/清除语义、生效优先级、测试语义。
- `style-prompt-localization`: 修订「可插拔翻译提供者链」为混合策略（词典全覆盖优先）。
- `web-ui-design`: 视觉变更声明与基线更新；新增「侧栏「LLM 配置」导航与配置页」「魔法棒 LLM 增强交互」；修订「辅助按钮覆盖前确认」。

## Impact

- **后端**：`web/server.py`（settings 字段与校验、`/api/llm/test`、`/api/llm/enhance`、翻译与增强的配置接线）、`src/yue2/style_localization.py`（混合链、配置合并、超时上限放宽至 60 秒）。
- **前端**：`web/static/index.html`（侧栏项 + `#view-llm`）、`web/static/app.js`（配置页、魔法棒改造、i18n 中英）；样式复用既有组件（预期不改 `styles.css` 令牌）。
- **测试**：`tests/test_web_settings.py`、`tests/test_style_localization.py` 扩展；新增 `tests/test_web_llm.py`。
- **基线**：`docs/ui-baseline/{en,zh}/` 全量重截 + `llm.png`×2。
- **文档**：`packaging/使用说明.md`。
- **风险**：中低——api_key 明文本地存储（已声明）；增强质量依赖所配模型（测试连接 + 失败降级 + 原文保留）；翻译链语义变化（词典优先全覆盖）需回归既有测试。
