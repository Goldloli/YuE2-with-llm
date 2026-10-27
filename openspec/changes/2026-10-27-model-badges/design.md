# Design: 2026-10-27-model-badges

## Context

模型页组件行由 `web/static/app.js` 的 `modelRowHtml()` 渲染，名称后仅在 `c.required` 为真时输出 `<span class="mdl-req">必备</span>`（`.mdl-req` 是既有胶囊样式：`--text-3` 文字、`--line` 描边、11px/600）。Windows 的 CUDA 套件行走独立分支 `cudaKitRowHtml()`，目前名称后无徽标。服务端 `_models_payload()` 为每个组件都带 `required` 布尔（核心模型 true，其余 false；CUDA 套件条目也是 false）。

## Goals / Non-goals

**Goals**：每一行都有且只有一个状态徽标；必备/可选文案走 i18n；视觉沿用既有胶囊；更新基线截图。

**Non-goals**：不改变行布局、间距、字号、颜色令牌；不把可选组件隐藏或排序；不改下载逻辑与接口；不给「已安装」等状态徽标换样式。

## Decisions

- **D1 复用 `.mdl-req`**：必备与可选共用同一胶囊样式，只换文案（避免引入新的视觉层级/令牌）；不新增 CSS。
- **D2 渲染位置**：`<div class="mdl-name">${label} ${badge}</div>`，徽标紧跟名称（与现状一致）。
- **D3 覆盖 CUDA 套件行**：该行在 `cudaKitRowHtml()` 中同样输出固定 `可选` 徽标（其 `required` 恒为 false），保持「所有行都有标注」。
- **D4 i18n**：新增 `models.optional`（en `optional` / zh `可选`），位置紧邻 `models.required`。
- **D5 基线**：仅重截 `models.png`（en/zh，1440×900），其余基线沿用；重截在默认端口 9086 的服务上进行。

## Risks

- 一行两个徽标（名称 + 右侧已安装状态）易混淆 → 左侧徽标是「是否必备」，右侧是「安装状态」，文案不同（必备/可选 vs 已安装/未安装），语义清晰。
- 截图重截后与旧基线有差异 → 属本变更声明的视觉变更（新增徽标），其余应无差异。
