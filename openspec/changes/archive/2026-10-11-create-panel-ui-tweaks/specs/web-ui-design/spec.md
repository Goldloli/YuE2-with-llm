# Spec Delta: web-ui-design（冻结基线的显式修订）

## ADDED Requirements

### Requirement: 创作面板卡片缝隙

创作面板的模式容器（`#pane-simple`、`#pane-advanced`）MUST 以 flex 纵列布局分隔各 `.cp-card`，卡片间距 MUST 为 16px。卡片自身的圆角、底色、内边距 MUST NOT 改变。

#### Scenario: 高级模式卡片分隔

WHEN 创作面板处于高级模式
THEN 歌词、风格、更多选项等相邻卡片之间有 16px 可见缝隙，卡片样式与令牌不变

### Requirement: 风格卡清空按钮

高级模式的风格卡头部 MUST 提供清空按钮（复用 `.cp-tool` 模式与 Phosphor trash 图标），点击 MUST 清空风格输入框并触发其 `input` 事件。按钮视觉 MUST 与「更多选项」卡的重置按钮一致。

#### Scenario: 一键清空风格

WHEN 风格输入框非空且用户点击清空按钮
THEN 输入框清空，依赖其内容的表单状态（如创作按钮禁用态）同步刷新

### Requirement: 时长控制一级入口

「更多选项」MUST 直接包含「长度上限（秒）」字段（number input，5–360，留空为自动），映射到既有 `max_seconds` 请求参数；「高级采样」二级折叠内 MUST NOT 再出现同义字段。字段的视觉 MUST 复用 `.cp-field` 既有模式。

#### Scenario: 设置时长并提交

WHEN 用户在「更多选项」填入 20 并创作
THEN 请求体包含 `max_seconds: 20`，页面上不存在第二个时长字段
