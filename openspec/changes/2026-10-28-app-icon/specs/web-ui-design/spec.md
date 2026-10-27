## ADDED Requirements

### Requirement: 应用图标

仓库 MUST 提供项目自有的应用图标资产：`assets/app-icon.png`（1024×1024，透明圆角，正方形）与 `web/static/app-icon.png`（favicon 尺寸）。`web/static/index.html` 的 favicon MUST 指向该图标（MUST NOT 再指向 `aura.jpg`），并 MUST 提供 `apple-touch-icon`；`README.md` MUST 在顶部展示该图标。图标 MUST 使用既有品牌色（`--pink`/强调橙）与暗色主体，MUST NOT 替换或移除侧栏 `YuE²` 字标、Create 按钮 aura 渐变等既有品牌元素。

#### Scenario: 浏览器标签图标

WHEN 用户打开 YuE2 Studio 页面
THEN 标签页显示项目应用图标（`/static/app-icon.png` 返回 200，`index.html` 不再引用 `aura.jpg` 作为 favicon）

#### Scenario: 仓库展示

WHEN 用户在 GitHub / 本地阅读 README
THEN 顶部显示 `assets/app-icon.png` 图标
