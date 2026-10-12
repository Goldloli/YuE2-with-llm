# Tasks: create-panel-ui-tweaks

## 1. 卡片缝隙

- [x] 1.1 `web/static/styles.css`：`#pane-simple, #pane-advanced` 增加 `display: flex; flex-direction: column; gap: 16px;`；验证：高级模式下歌词/风格/更多选项三卡之间有 16px 缝隙，简单模式单卡渲染无异常

## 2. 风格卡清空按钮

- [x] 2.1 `web/static/index.html`：风格卡 `cp-card-head` 内加 `cp-card-tools` + `#style-clear`（`.cp-tool` + `ph-trash`）；`web/static/i18n.js` 加 `tip.clearStyle`（en/zh）；验证：按钮外观与「更多选项」重置按钮一致
- [x] 2.2 `web/static/app.js`：绑定点击 → 清空 `#adv-style` 并派发 `input` 事件；验证：点击后风格框为空、创作按钮禁用态正确刷新

## 3. 时长控制提升

- [x] 3.1 `web/static/index.html`：「长度上限（秒）」字段从「高级采样」折叠移至「更多选项」一级（歌曲标题之后），id 改为 `adv-maxsec`，采样折叠内删除原 `#sam-maxsec` 字段；验证：页面只有一个时长字段
- [x] 3.2 `web/static/app.js`：提交映射、表单清空、快照恢复三处 wiring 全部改为 `#adv-maxsec`，grep 确认 `sam-maxsec` 零残留；验证：设置 20 秒提交，请求体含 `max_seconds: 20`；清空表单后字段复位；从历史歌曲恢复表单时时长正确回填
- [x] 3.3 服务端行为验证：生成一首 20 秒歌曲，确认产出时长约 20 秒（既有 `max_seconds` → `max_tokens` 换算路径不变）

## 4. 校验与归档

- [x] 4.1 `openspec validate create-panel-ui-tweaks --strict` 通过
- [x] 4.2 重截 `docs/ui-baseline/{en,zh}/` 创作面板页，与旧基线对照确认仅声明的三处有差异，然后更新基线截图
- [x] 4.3 归档变更并 `codegraph sync`
