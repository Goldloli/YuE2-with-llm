# Proposal: share-button-to-download

## Why

界面上的「分享」按钮实际行为是**下载音频**（`data-action="download"` → `/api/songs/{id}/audio`），但图标是分享箭头、文案是「分享 / Share」，名实不符。用户要求改为「下载」。

## What Changes

**本提案包含视觉变更（按 `web-ui-design` 规格显式声明）**，影响范围：按钮的图标与文案两处（控件形态、尺寸、配色、布局均不变）：

1. **歌曲行按钮**（`app.js:314`）：图标 `ph-share` → `ph-download`，文案键由 `row.share`（分享/Share）更名为 `row.download`（下载/Download）；
2. **详情面板图标按钮**（`app.js:477`）：图标 `ph-share` → `ph-download`（tooltip 已为 `detail.download`「下载」，不改）；
3. **右键菜单**（`app.js:1017`）：`ph-share` → `ph-download`（菜单文案 `menu.download` 已为「下载」，不改）；
4. i18n：`row.share` 键更名为 `row.download` 并更新两语文案；确认无其他引用后删除旧键。

非目标（Non-goals）：不改下载行为本身（端点、文件名）；不加「分享链接」类新功能；不动播放条与其他按钮。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `web-ui-design`: 冻结基线的显式修订——歌曲行/详情面板/右键菜单的下载入口统一为下载图标与「下载」文案。

## Impact

- **代码**：`web/static/app.js`（三处图标与一处文案键）、`web/static/i18n.js`（键更名，en/zh）。
- **基线截图**：歌曲行的按钮文案出现在工作区列表（create 页基线两张），详情面板图标按钮出现在 detail 页基线——`docs/ui-baseline/{en,zh}/` 的 **create-simple、create-advanced、detail 共 6 张** 需重截（library 网格基线为悬停前状态不含该按钮，settings 无关）。
- **测试**：无 pytest 前端断言；浏览器实测三处入口文案/图标 + 下载触发；基线对照确认除声明项外零差异。
- **风险**：低——纯图标/文案级变更，行为路径不变。
