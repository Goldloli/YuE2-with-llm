# Design: show-original-style-in-ui

## Context

`style-prompt-localization` 已归档生效：Web 端 `public()` 响应已包含 `style_original`。前端在 `app.js` 中渲染 style 文本的位置有三类：歌曲行 `.row-style`（feed 与 library 共用渲染函数）、详情页 `.detail-style`、以及少量使用 style 的次要位置（如编辑/分享弹窗的 from 描述）。

## Goals / Non-Goals

**Goals:** 用户在所有展示位置看到自己输入的中文原文；英文标签仍可通过 tooltip 查看（可调试性）。

**Non-Goals:** 不动翻译机制、持久化、CLI/MLX；不动任何 CSS/布局/组件结构（冻结基线）。

## Decisions

### D1: 绑定层修正 `style_original ?? style`，不改数据模型

`public()` 已返回 `style_original`，前端只需在渲染 style 文本处统一改为 `song.style_original || song.style`，并加 `title=style`（英文标签）。无 DOM 结构/类名变化，freeze-compliant。

备选：服务端把 `style` 直接换回中文展示——会破坏 API 语义（`style` 是模型实际输入），否决。

### D2: 词典补词走实测驱动

只补实测中观察到的遗漏与明显高频词：`五声音阶→pentatonic scale`、`反拍→offbeat`、`慵懒→laid-back`、`烟雨江南→misty Jiangnan ambience`、`慢板→slow ballad`（核查是否已覆盖）。诗意短语（如烟雨江南）映射到最接近的音乐氛围标签；无法合理映射的不强行收录（保留原文是规格允许的行为）。

### D3: 编辑/分享弹窗同步显示原文

凡展示 style 的弹窗（Remix/Edit/Share 的 from 描述）同样走 `style_original ?? style`，避免列表与弹窗不一致。

## Risks / Trade-offs

- [tooltip 依赖 title 属性，移动端不可见] → 接受：桌面端工具定位，移动端暂不覆盖。
- [详情页看不到英文标签，调试不便] → tooltip 保留；开发场景可查 request.json。

## Migration Plan

纯前端展示绑定 + 词典数据，无迁移。回滚即还原绑定表达式。
