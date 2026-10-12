# Proposal: support-chinese-style-prompts

## Why

YuE2 的 `style`/`tags` 提示词目前只能用英文：checkpoint 的原生协议（`PROTOCOL_VERSION = "yue2-native-v1"`）按「英文 instruction + 英文 `[Tags]` 标签」训练，推理管道对 style 文本不做任何归一化或翻译（`src/yue2/protocol.py:108`），中文风格描述会被原样传给模型，导致风格跟随明显变弱。同时 Web UI 的中文占位符（`web/static/i18n.js:304,308`）正在主动诱导用户输入中文提示词，嗓音按钮还会向中文文本追加英文后缀（`web/static/app.js:656`），现状自相矛盾。歌词（lyrics）不受此限——byte-level BPE 原生支持中文，无需改动。

## What Changes

- 新增「style 提示词本地化」层：在请求构建前检测 style 语言，中文 style 自动翻译为英文标签后再进入 `SongRequest.text()` 模板。
- 翻译发生在请求身份哈希（`src/yue2/pipeline.py:382`）**之前**，且持久化到 `request.json` 的是翻译后的英文文本，保证运行可复现、可校验。
- 翻译提供者可插拔：优先使用用户配置的 LLM 端点；无配置时回退到内置的「中文音乐术语 → 英文标签」词典 + 模板规则；均不可用时原样透传并告警。
- 新增配置开关：`--style-language auto|en|off`（CLI）与 Web 设置项，默认 `auto`（检测到中文即翻译）。
- 修复 Web UI 嗓音按钮向中文 style 追加英文 `", male/female vocals"` 后缀的问题：追加在翻译之后的英文标签上。
- 非目标（Non-goals）：不改 lyrics 处理（中文歌词已原生支持）；不改模型、模板或训练；不做中文标签直推模型（双语 `[Tags]`）——该路线需质量基准对比，留作后续提案。

## Capabilities

### New Capabilities
- `style-prompt-localization`: 在请求构建前对 style 提示词做语言检测与中译英，含可插拔翻译提供者、词典回退、配置开关与持久化约束。

### Modified Capabilities

（无 —— `openspec/specs/` 当前为空，本变更不修改任何既有能力规格。）

## Impact

- **代码**：`src/yue2/protocol.py`（或新增 `src/yue2/style_localization.py`）、`src/yue2/cli.py`（`request_kwargs` / 新 CLI flag）、`web/server.py`（`queue_from_request`）、`web/static/app.js`（嗓音后缀时序）、`tools/mlx_generate.py`（MLX 路径同样接入）。
- **API**：CLI 新增 `--style-language`；`YuE2Pipeline.__call__` 新增可选参数；`request.json` 中 style 字段语义变为「翻译后的英文」，原始中文存入新字段（如 `style_original`）。
- **依赖**：可选 LLM 端点配置（不新增硬依赖）；内置词典为纯数据文件。
- **测试**：新增针对中文输入最终 `[Tags]` 块内容、持久化字段、透传回退的测试，风格对齐 `tests/test_text_encoding.py` / `tests/test_protocol.py`。
- **文档**：`AGENTS.md`「提示词现状」、`skills/yue2-music/SKILL.md`、`docs/generation.md` 更新。
- **前端冻结合规**：本变更对 `web/static/` 的改动（嗓音后缀改由后端拼接）属不可见行为修复，MUST 不产生任何视觉差异，遵守 `web-ui-design` 冻结基线（见 `freeze-web-ui-design` 变更），无需视觉变更声明。
