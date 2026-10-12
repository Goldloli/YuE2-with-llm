# Proposal: show-original-style-in-ui

## Why

中文提示词支持上线后，Web UI 的歌曲行/详情页显示的是**翻译后的英文标签**（`style` 字段），而不是用户输入的中文原文（`style_original`）。用户看到英文会误以为中文提示词没生效（实际已生效，翻译是设计机制），且译文中夹杂未收录的中文残留词，观感混乱。同时实测暴露了词典的几个高频遗漏词（五声音阶、反拍、慵懒、烟雨江南）。

## What Changes

- Web UI 所有展示 style 的位置（歌曲流列表、音乐库、详情页）改为：存在 `style_original` 时显示中文原文，否则显示 `style`；英文标签移到 tooltip（`title` 属性），不产生新的可见元素或样式变化。
- 补充内置词典遗漏词条：`五声音阶→pentatonic scale`、`反拍→offbeat`、`慵懒→laid-back`、`烟雨江南→misty Jiangnan ambience` 等实测中未命中的词。
- 非目标（Non-goals）：不改翻译机制与持久化格式；不改任何样式/布局/组件视觉（遵守 `web-ui-design` 冻结基线，本变更为数据绑定修正，无视觉差异）；不改 CLI/MLX 输出。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities
- `style-prompt-localization`: 新增需求——Web UI 必须向用户展示其原始输入（`style_original`），英文标签仅作为次级信息（tooltip）。

## Impact

- **代码**：`web/static/app.js`（style 展示绑定改为 `style_original ?? style` + tooltip）、`src/yue2/data/zh_style_terms.json`（补词）。
- **API**：无变更（`public()` 已返回 `style_original`）。
- **测试**：词典新词条用例；现有测试保持绿色。
- **前端冻结合规**：复用 `.row-style`/`.detail-style` 既有类，仅替换文本内容与增加 `title` 属性，零视觉样式变化，无需视觉变更声明。
