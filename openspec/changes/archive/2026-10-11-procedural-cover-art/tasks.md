# Tasks: procedural-cover-art

## 1. 生成器

- [x] 1.1 `web/static/app.js`：新增 `coverArt(id)` 确定性生成器（mulberry32 种子 + 流场笔触 + 暗角 + 颗粒，256px canvas → dataURL）与 `Map` 缓存；验证：同一 id 两次生成 dataURL 完全一致
- [x] 1.2 `coverStyle(id)` 改写为消费缓存 dataURL（`background-image/cover/background-color`），保留原渐变实现为回退；验证：四处调用点零改动生效

## 2. 浏览器实测

- [x] 2.1 四处封面（列表行 84px、库网格、详情面板 240px、播放条 46px）渲染正确、无拉伸变形；验证：截图逐一检查
- [x] 2.2 确定性：刷新页面、切换视图后同一首歌封面不变；不同歌曲封面各不相同；验证：连续刷新对比 + 多首并排
- [x] 2.3 性能与回退：全库首屏加载无可见卡顿；控制台无报错
- [x] 2.4 缩略图观感：84px 与 46px 下纹理仍可辨、不糊成色块

## 3. 基线更新

- [x] 3.1 重截 `docs/ui-baseline/{en,zh}/` 五张（create-simple/create-advanced/library/detail/settings），对照旧基线确认**仅封面**有差异（settings 页面若无封面则应与旧图一致）

## 4. 校验与归档

- [x] 4.1 `openspec validate procedural-cover-art --strict` 通过；归档；`codegraph sync`
