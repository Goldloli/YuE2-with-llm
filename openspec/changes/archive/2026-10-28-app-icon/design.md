# Design: 2026-10-28-app-icon

## Context

界面为暗色三栏 + 品红/橙渐变（`--pink: #e93581`、强调橙 `#e8622c`、`--bg: #101012`）。README 现为纯文字；`web/static/index.html` 的 favicon 指向 `aura.jpg`。品牌元素契约（`web-ui-design`）要求保留侧栏 `YuE²` 字标、Create 按钮 aura 渐变与 Phosphor 图标，本次不触碰。

## Decisions

- **D1 图形方案**：黑胶唱片正面 + 中心渐变标签 + 贯穿波形曲线；品红→橙渐变与既有品牌色一致，32px 下仍可辨认（波形+圆形轮廓）。
- **D2 资产尺寸**：源图 1024×1024 透明圆角（四周留白 4%）；256 供 README/通用；favicon 256 PNG（浏览器自行缩放）；apple-touch-icon 180。
- **D3 集成点**：`index.html` favicon + apple-touch-icon；README 顶部 128px 图标；不替换 `assets/logo.png`（上游 YuE 素材保持原样）。
- **D4 缓存**：图标路径为全新静态文件（`/static/app-icon.png`），无旧缓存问题；不需要改 `?v=` 版本号。
- **D5 验证**：pytest 断言资产为正方形 PNG、`index.html` 与 README 引用存在；启动服务 `GET /static/app-icon.png` 返回 200。

## Risks

- 透明背景在浅色阅读器（如 GitHub dark/light）下可能边缘发白 → 已用透明圆角 + 深色主体，两套主题均可读。
- 源图为 1254 生成，缩至 32px 细节（唱片纹路）会弱化 → 波形与橙红中心仍保留识别度。
