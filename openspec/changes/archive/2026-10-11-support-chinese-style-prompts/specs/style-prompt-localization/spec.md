# Spec Delta: style-prompt-localization

## Purpose

在请求构建前对 style/tags 提示词做语言检测与中文→英文标签翻译，使中文用户可以用自然语言描述风格，同时保持模型输入协议（英文 `[Tags]`）与运行结果的可复现性不变。

## ADDED Requirements

### Requirement: 中文 style 检测

系统 SHALL 在组装模型输入模板之前，检测 style/tags 文本是否包含中日韩统一表意文字（CJK）。纯英文（含数字、标点、现有英文标签）的 style MUST 被判定为无需翻译。

#### Scenario: 纯中文 style

WHEN 用户提交 style「雷鬼，小调合唱，木管，流行电子」且模式为 `auto`
THEN 系统判定其包含中文，进入翻译流程

#### Scenario: 纯英文 style

WHEN 用户提交 style「reggae, minor choir, woodwinds, electro pop」且模式为 `auto`
THEN 系统判定其不含中文，style 原样通过，不发生任何提供者调用

#### Scenario: 中英混合 style

WHEN 用户提交 style「Mandarin, 温暖钢琴, acoustic pop」且模式为 `auto`
THEN 系统判定其包含中文进入翻译流程，且翻译输出 MUST 保留原有英文标签的语义

### Requirement: 翻译后进入模板

判定为中文的 style SHALL 被翻译为英文逗号分隔标签，且进入 `SongRequest.text()` 的 `[Tags]` 块的 MUST 是翻译后的英文文本。歌词（lyrics）MUST 保持原样，不做任何语言检测或翻译。

#### Scenario: 模板内容纯净

WHEN 中文 style 完成翻译
THEN 最终 `[Tags]` 块内容为英文标签，模型输入模板结构与英文输入时完全一致

#### Scenario: 歌词不受影响

WHEN 用户提交中文 style 与中文歌词
THEN 仅 style 被翻译，歌词逐字保留在 `[Lyrics]` 块中

### Requirement: 可插拔翻译提供者链

系统 SHALL 按以下顺序尝试翻译提供者：(1) 用户配置的 LLM 端点；(2) 内置中文音乐术语词典与模板规则；(3) 原样透传并输出可见告警。任一提供者失败 MUST 自动降级到下一级，不得中断生成。

#### Scenario: LLM 端点可用

WHEN 用户配置了 LLM 端点且端点可达
THEN 使用 LLM 完成翻译，输出英文标签

#### Scenario: 回退到内置词典

WHEN 未配置 LLM 端点或端点调用失败
THEN 使用内置术语词典与规则完成翻译，词典未覆盖的词按通行译法或拼音/原文附后的方式处理

#### Scenario: 全部不可用

WHEN 无任何提供者可用
THEN style 原样透传，并在日志/Web UI 输出「未翻译」告警，生成流程不中断

### Requirement: 持久化与可复现

翻译 SHALL 发生在请求身份哈希计算之前。持久化的 `request.json` MUST 同时包含翻译后的 `style`（英文，参与哈希与生成）与 `style_original`（用户原始输入）。再次运行同一请求 MUST 产生与首次一致的身份与输出路径。

#### Scenario: 持久化字段

WHEN 中文 style 请求被持久化
THEN `request.json` 中 `style` 为英文标签、`style_original` 为中文原文

#### Scenario: 复现一致

WHEN 使用同一 `request.json` 重新运行
THEN 不再触发翻译，身份哈希与首次运行一致

### Requirement: 配置开关

系统 SHALL 提供 `auto | en | off` 三档 style 语言模式（CLI flag 与 Web 设置），默认 `auto`。`en` 或 `off` 时 MUST 完全跳过检测与翻译，行为与当前版本一致。

#### Scenario: 显式关闭

WHEN 用户设置 `--style-language off` 并提交中文 style
THEN style 原样透传，且不产生翻译告警之外的任何行为变化

### Requirement: Web 嗓音后缀时序

Web UI 的嗓音按钮（male/female vocals）追加的英文后缀 MUST 作用于翻译完成后的英文 style，不得拼接到未翻译的中文文本上。

#### Scenario: 中文 style + 嗓音按钮

WHEN 用户在 Web UI 输入中文 style 并选择「女声」
THEN 追加 `female vocals` 发生在翻译之后，最终 `[Tags]` 块为纯英文
