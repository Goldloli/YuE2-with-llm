# Proposal: freeze-web-ui-design

## Why

当前 Web 前端（`web/static/`）采用暗色三栏音乐工作台视觉（`styles.css` 第 1 行注明主题说明），用户对现有视觉风格与布局完全满意，希望它成为**冻结基线**：之后的任何功能改动（包括进行中的中文提示词支持）都不得改变这套风格。目前这种约束只存在于口头约定，没有机制保证后续变更（人或 AI 执行）不偏离。

## What Changes

- 新增 `web-ui-design` 能力规格，把当前 Suno 风格固化为行为契约：设计令牌（颜色/字体/圆角）、三栏布局 + 底部播放栏、组件语言（pill 按钮、卡片、song-row、modal、toast 等）、品牌元素（aura 渐变 CTA、Phosphor 图标）与克制的动效时长。
- 建立变更管控规则：任何会改变外观/布局/组件视觉的提案 MUST 在 proposal 中显式声明「视觉变更」，经用户确认后方可实施；纯文案/i18n、后端逻辑、bug 修复不属于视觉变更。
- `AGENTS.md` 增加「前端风格冻结」一节，指向该规格，作为 AI 助手层面的执行保障。
- 抓取一套基线截图（固定视口、en/zh 双语）存 `docs/ui-baseline/`，作为人工审查参照（非自动化像素门禁）。
- 非目标（Non-goals）：不重构前端代码、不引入视觉回归测试框架、不改动任何现有样式——本变更只立契约与保障机制。

## Capabilities

### New Capabilities
- `web-ui-design`: Web 前端的 Suno 风格设计基线与变更管控契约，覆盖设计令牌、布局结构、组件语言、品牌元素、动效克制与视觉变更声明义务。

### Modified Capabilities

（无 —— `openspec/specs/` 当前为空。）

## Impact

- **规格/文档**：新增 `openspec/specs/web-ui-design`（归档后生效）；`AGENTS.md` 新增冻结规则；`docs/ui-baseline/` 新增基线截图。
- **代码**：零改动。
- **流程**：后续所有触及 `web/static/` 的 OpenSpec 提案须对照该规格自查；视觉变更须显式声明。
- **关联**：进行中的 `support-chinese-style-prompts` 变更（嗓音后缀改后端拼接）属于行为修复而非视觉变更，不受影响，但实施时须遵守本基线。
