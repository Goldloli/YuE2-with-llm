# Tasks: share-button-to-download

## 1. 实现

- [x] 1.1 `app.js` 三处：歌曲行按钮（314，图标 + 文案键）、详情面板图标按钮（477）、右键菜单（1017）统一为 `ph-download`
- [x] 1.2 `i18n.js`：`row.share` 更名为 `row.download`（en "Download" / zh "下载"）；grep 确认无残留引用
- [x] 1.3 浏览器实测：工作区列表按钮、详情面板按钮、右键菜单三处显示「下载」+ 下载图标；点击触发音频下载

## 2. 基线

- [x] 2.1 重截 `docs/ui-baseline/{en,zh}/` 的 create-simple、create-advanced、detail 共 6 张；对照确认除按钮图标/文案外零差异

## 3. 校验

- [x] 3.1 `openspec validate share-button-to-download --strict`；归档；`codegraph sync`
