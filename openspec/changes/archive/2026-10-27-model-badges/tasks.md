# Tasks: 2026-10-27-model-badges

## 1. 前端徽标

- [x] 1.1 `web/static/app.js` `modelRowHtml()`：名称后统一输出徽标——`c.required` 为真 →「必备」，否则 →「可选」，复用 `.mdl-req` 样式
- [x] 1.2 `web/static/app.js` `cudaKitRowHtml()`：CUDA 套件行名称后输出「可选」徽标
- [x] 1.3 `web/static/i18n.js`：新增 `models.optional`（en `optional` / zh `可选`），紧邻 `models.required`

## 2. 基线与验证

- [x] 2.1 重截 `docs/ui-baseline/{en,zh}/models.png`（1440×900，默认端口 9086）——每行带必备/可选徽标
- [x] 2.2 `pytest` / `actionlint` 通过；人工核对模型页 en/zh 截图无其它视觉差异

## 3. 打包与发布

- [x] 3.1 push main → 滚动包 CI 更新（含新前端）
- [x] 3.2 打 `v0.1.10` → 双平台自包含包构建 + 真冒烟 + 发布；重建本地 mac 包
- [x] 3.3 归档变更
