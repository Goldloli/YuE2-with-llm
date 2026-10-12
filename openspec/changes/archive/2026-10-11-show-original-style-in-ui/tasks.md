# Tasks: show-original-style-in-ui

## 1. 前端展示修正

- [x] 1.1 `web/static/app.js`：feed/library 歌曲行与详情页的 style 文本改为 `style_original || style`，并加 `title`（英文标签）；验证：两首中文测试歌曲（untitled-11633、song-11993）在 UI 中显示中文原文，英文歌曲显示不变，页面 DOM 结构/类名零变化
- [x] 1.2 Remix/Edit/Share 等弹窗的 from 描述同步显示原文；验证：弹窗文本与列表一致

## 2. 词典补词

- [x] 2.1 向 `src/yue2/data/zh_style_terms.json` 补充实测遗漏词条（五声音阶/反拍/慵懒/烟雨江南，核查慢板等是否已覆盖）；验证：`localize_style("中国风，古筝，五声音阶，抒情慢板，70 BPM", "auto")` 输出无中文残留
- [x] 2.2 更新 `tests/test_style_localization.py` 相关用例并全量回归；验证：`pytest` 全绿

## 3. 校验与归档

- [x] 3.1 `openspec validate show-original-style-in-ui --strict` 通过；验证：无 error
- [x] 3.2 归档变更，确认 `openspec/specs/style-prompt-localization/spec.md` 追加新需求；验证：`openspec list` 无活动变更，spec 含「原始输入展示」
