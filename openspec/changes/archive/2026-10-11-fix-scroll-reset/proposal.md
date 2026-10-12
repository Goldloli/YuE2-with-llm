# Proposal: fix-scroll-reset

## Why

用户报告：某些页面滑到底后会自动跳回顶部。浏览器实测复现（模型页）：内容 1255px / 视口 786px，滚到底（scrollTop 469）后**2.2 秒内归零**。

根因：`renderModelsPage()` 每轮 1.5s 轮询都整体替换 `#view-models`.innerHTML——而滚动容器 `.mdl-scroll` 就在被替换的子树内，元素被销毁重建 → scrollTop 归零。

同类问题排查（同模式：滚动容器位于被替换的子树内）：
- **详情面板**：`#detail-content` 自身是滚动容器且被 `renderDetail` 整体替换——软刷新（生成中每隔数秒 sig 变化）时滚动位置丢失；
- **设置弹窗**：`#modal` 自身是滚动容器且 `openSettings()` 整体替换——在底部点击任一设置项后跳回顶部。

（对照：工作区/音乐库列表无恙——其滚动容器 `.feed-body` 是列表元素的祖先，不参与替换。）

## What Changes

（行为修复，无视觉变化，无基线更新）

1. **模型页（`renderModelsPage`）**：
   - 轮询 payload 与上次相同且无本地状态变化时**跳过重建**（空闲零 DOM 抖动）；
   - 需要重建时（下载进度变化、设置切换）保留并恢复 `.mdl-scroll` 的 scrollTop。
2. **详情面板（`renderDetail`）**：软刷新（同一歌曲 id）时保留并恢复 `#detail-content` 的 scrollTop；切换到另一首歌（id 变化）时保持重置到顶部（期望行为，不保留）。
3. **设置弹窗（`openSettings`）**：重建时保留并恢复 `#modal` 的 scrollTop（点击底部设置项不再跳顶）。
4. 非目标：不改任何页面布局/样式/内容；不改列表页（本就无恙）；不引入滚动位置持久化（会话级恢复即止）。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `web-ui-design`: 冻结基线显式修订——新增「重渲染保持滚动位置」行为要求（纯行为，无视觉变更、无基线影响）。

## Impact

- **代码**：`web/static/app.js` 三处（renderModelsPage / renderDetail / openSettings 各数行）。
- **测试**：浏览器复现脚本回归（滚底 → 跨轮询 → 位置不变；切歌 → 回顶部）；无 pytest 前端断言。
- **风险**：极低。滚动恢复模式在既有代码中已有先例（详情面板的 `.tech` 展开态、分数报告即用「重建前保存、重建后恢复」手法）。
