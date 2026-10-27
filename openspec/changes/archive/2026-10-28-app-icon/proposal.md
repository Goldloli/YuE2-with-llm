# Proposal: 2026-10-28-app-icon

## Why

项目此前没有自己的应用图标：浏览器标签沿用 `aura.jpg` 渐变素材，README 没有品牌图形，GitHub 仓库也没有视觉标识。用户要求为 YuE2 Studio 生成图标，并选定「黑胶唱片 + 波形 + 品红→橙渐变」方案。

## What Changes

- **视觉变更（用户已明确要求并选定方案）**：新增 YuE2 Studio 应用图标资产：
  - `assets/app-icon.png`（1024×1024，透明圆角版）与 `assets/app-icon-256.png`（256×256）；
  - `web/static/app-icon.png`（256，favicon）与 `web/static/apple-touch-icon.png`（180）；
  - `web/static/index.html` 的 `<link rel="icon">` 由 `aura.jpg` 改为新图标，并新增 `apple-touch-icon`；
  - `README.md` 顶部展示图标（128px，居中）。
- **不改变**：页面布局、侧栏 `YuE²` 字标、设计令牌、`aura.jpg`（仍用于主行动按钮与渐变）。
- **规格**：ADDED `web-ui-design`「应用图标」要求（资产位置、favicon 引用、README 展示、不得替换字标）。
- **发布**：更新滚动包；打 `v0.1.12` 发布双平台正式包；重建本地 mac 包。

## Capabilities

### Modified Capabilities

- `web-ui-design`：新增品牌应用图标（favicon/README），不触及既有布局与字标契约。

## Impact

- 新增：`assets/app-icon.png`、`assets/app-icon-256.png`、`web/static/app-icon.png`、`web/static/apple-touch-icon.png`、`tests/test_app_icon.py`。
- 修改：`web/static/index.html`、`README.md`。
- 兼容性：纯静态资源/标记变更，不影响接口、模型与打包结构。
