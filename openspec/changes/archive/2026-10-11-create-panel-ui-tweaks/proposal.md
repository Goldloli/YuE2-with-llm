# Proposal: create-panel-ui-tweaks

## Why

用户对创作面板提出三处体验改进：①各板块卡片贴在一起、缺少呼吸感；②风格框无法一键清空（写了不满意的风格只能手动全选删除）；③时长控制藏在「高级采样」二级折叠里，而该能力模型已支持（`max_seconds` → `max_tokens`，`web/server.py:454-457`），值得更显眼的入口。

## What Changes

**本提案包含视觉变更（按 `web-ui-design` 规格显式声明）**，影响范围仅限创作面板（`#create-panel`）：

1. **卡片缝隙（视觉变更）**：`#pane-simple` / `#pane-advanced` 增加 `display: flex; flex-direction: column; gap: 16px`，使创作面板内各 `.cp-card` 之间出现 16px 真实缝隙（现状：pane 无布局规则，卡片块级堆叠间距为 0；16px 与 `.cp-scroll` 水平 padding 一致，保持视觉节奏）。卡片自身样式（圆角、底色、padding）不变。
2. **风格卡清空按钮（视觉变更）**：高级模式风格卡头部右侧增加 `cp-card-tools` 工具区，复用 `.cp-tool` 模式放一个 trash 图标按钮 `#style-clear`（与「更多选项」卡的重置按钮同款），点击清空 `#adv-style` 并触发 `input` 事件（保持创作按钮禁用态逻辑一致）。新增 i18n 文案 `tip.clearStyle`（Clear styles / 清空风格）。
3. **时长控制提升（视觉变更）**：「长度上限（秒）」从「高级采样」二级折叠移出，作为一级字段放入「更多选项」：位置在「歌曲标题」之后、「随机种子 / CFG 强度」行之前，独占一个 `.cp-field`（全宽 number input，min 5 / max 360 / placeholder Auto，复用既有 `cp.maxSec` 文案）。字段 id 由 `#sam-maxsec` 改为 `#adv-maxsec`，「高级采样」折叠内同步移除该字段（避免两处同义字段）；`app.js` 的提交映射、表单清空、快照恢复三处 wiring 同步更新。语义不变，仍映射到既有 `max_seconds` 参数（5–360 秒，服务端校验不变）。

非目标（Non-goals）：不改三栏布局、设计令牌、组件语言、品牌元素；不改简单模式结构；不动 `max_seconds` 的服务端语义与上限换算；不改其他页面。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `web-ui-design`: 追加创作面板的三处获准视觉变更及其验收标准（卡片缝隙、风格清空按钮、时长字段位置），作为冻结基线的显式修订。

## Impact

- **代码**：`web/static/styles.css`（pane 布局规则一条）、`web/static/index.html`（风格卡工具区 + 时长字段移位）、`web/static/app.js`（`#style-clear` 绑定；`sam-maxsec` → `adv-maxsec` 三处 wiring）、`web/static/i18n.js`（`tip.clearStyle` en/zh）。
- **基线对照**：实施后须重截 `docs/ui-baseline/{en,zh}/` 的创作面板（简单 + 高级模式）页并与基线对照，确认除上述三处声明变更外无差异；基线截图随后更新为新状态。
- **测试**：现有 pytest 无前端断言，零影响；以浏览器实测 + 基线对照作为验收。
- **风险**：`adv-maxsec` 的 wiring 遗漏会导致时长不生效或残留字段重复提交——实施时须 grep `sam-maxsec` 确认零残留。
