# Tasks: detail-panel-drawer

## 1. 容器与版式

- [x] 1.1 `web/static/index.html`：`#view-detail` 的 Back 按钮改为 × 圆形关闭钮（`ph-x`，复用 `.cp-circle` 模式）；验证：DOM 结构就绪
- [x] 1.2 `web/static/styles.css`：`#main` 加 `position: relative`；`#view-detail` 改为右缘浮动玻璃面板（360px、距顶/右/底 12px、圆角 20px、`color-mix` 半透明 + `backdrop-filter: blur(18px) saturate(1.3)`、`@supports` 回退不透明、transform 滑入滑出 ≤0.18s、z-index 低于 modal）；`.detail-hero` 纵向、`.detail-cover` 居中正方形 ≤240px、`.detail-title` 24px、`.detail-pane` 自适应；验证：面板玻璃质感生效、列表透过模糊可见、滑入滑出流畅

## 2. 状态接线

- [x] 2.1 `web/static/app.js`：面板开启态改为 `state.detailId` 非空；`runAction("detail")`、行点击打开/原地切换；Esc 与 × 关闭；删除联动关闭；软刷新条件迁移；`state.detailFrom` 与 `showView("detail")` 全量清理；`loadVariant`/`openEdit`/`openCover` 等出口关闭面板；验证：grep 无 `detailFrom` 残留
- [x] 2.2 i18n：关闭钮 tooltip、复制按钮、转谱行文案（en/zh）；验证：均有文案

## 3. 生成歌曲信息展示

- [x] 3.1 `web/static/app.js` renderDetail：风格卡片（`.detail-style-card`，标题「风格」+ `dispStyle` 文本 + 复制按钮 `ph-copy`，点击复制显示文本并 toast；tooltip 英文标签保留）；验证：中文歌显示原文、复制内容正确
- [x] 3.2 `web/server.py`：`song_detail` 的 tech 读取列表加入 `transfer.json`；`web/static/app.js`：`d.transfer || tech["transfer.json"]` 时技术详情加「转谱」行（人声音符 N→0、Ins 音符数）；验证：`song-15323`（生成时转谱）与任一 cover（入队时转谱）均显示
- [x] 3.3 `web/static/app.js`：技术详情补 `cfg_scale`、`vocal_gender` 行（存在时）；验证：设置过 CFG 的歌曲显示，未设置的不显示空行
- [x] 3.4 上传条目回归：详情仍为现有占位展示，无新增推断内容

## 4. 浏览器实测

- [x] 4.1 打开/切换/关闭/Esc/删除当前歌/生成中进度刷新，六条路径逐一过；风格卡片/转谱行/参数行渲染正确
- [x] 4.2 重截 `docs/ui-baseline/{en,zh}/detail.png`（面板开启态），对照 create/library/settings 基线确认零意外差异

## 5. 校验与归档

- [x] 5.1 `openspec validate detail-panel-drawer --strict` 通过；归档；`codegraph sync`
