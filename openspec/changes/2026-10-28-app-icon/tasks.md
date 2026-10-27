# Tasks: 2026-10-28-app-icon

## 1. 资产与集成

- [x] 1.1 生成并选定图标方案（黑胶 + 波形 + 品牌渐变），产出 `assets/app-icon.png`(1024)、`assets/app-icon-256.png`
- [x] 1.2 生成 web 静态图标：`web/static/app-icon.png`(256)、`web/static/apple-touch-icon.png`(180)
- [x] 1.3 `web/static/index.html`：favicon 改指向新图标并补 `apple-touch-icon`
- [x] 1.4 `README.md` 顶部展示 128px 图标

## 2. 测试与验证

- [ ] 2.1 新增 `tests/test_app_icon.py`（资产为正方形 PNG、index.html/README 引用、README 展示宽度）
- [ ] 2.2 `pytest` / `actionlint` 通过；本地起服务验证 `/static/app-icon.png` 200

## 3. 打包与发布

- [ ] 3.1 push main → 滚动包 CI 更新
- [ ] 3.2 打 `v0.1.12` → 双平台自包含包构建 + 真冒烟 + 发布；重建本地 mac 包
- [ ] 3.3 归档变更
