# Tasks: fix-instrumental-vocals

## 1. 风格标签强化

- [x] 1.1 `src/yue2/style_localization.py` 新增 `ensure_instrumental_tag(style)`：大小写不敏感判重，缺失时追加 `, instrumental`；验证：含 `Instrumental` 的输入原样返回，空串/纯空白安全返回
- [x] 1.2 `web/server.py queue_song`：`instrumental=True` 时在本地化之后调用 `ensure_instrumental_tag`；`style_original` 不变；验证：创建与 cover 两条路径入队歌曲的 `style` 均含 `instrumental` 标签

## 2. Vocal→Ins 确定性转谱

- [x] 2.1 `web/server.py` 新增转谱辅助（subprocess 调 `skills/yue2-music/instrumental/scripts/instrumentalize.py` CLI，超时与错误捕获）；验证：对 `outputs/2-12753/score.abc` 转谱后 Vocal 声部 0 音符，产出 `transfer.json`
- [x] 2.2 入队已有 ABC 路径（cover/edit）：`queue_song` 在 `instrumental=True` 且 `abc` 非空时先转谱再入队；失败回退原谱并记 `instrumental_warning`；验证：用含 Vocal 音符的谱发起 instrumental cover，入队 `abc` 的 Vocal 全休止
- [x] 2.3 torch `_generate`：`pipe.plan()` 后若 `instrumental` 且 Vocal 有声符，转谱 → `dataclasses.replace(request, abc=converted)` 重建 plan；输出目录写 `score.model.abc` + `transfer.json`；验证：开启纯音乐生成一首短歌，`score.abc` Vocal 全休止、两谱并存
- [x] 2.4 MLX：`tools/mlx_generate.py` 新增 `--instrumental`（sys.path 注入 `instrumental/scripts`，plan 后同进程转谱续渲；`--plan-only` 时不转谱）；`web/server.py _generate_mlx` 按歌曲 `instrumental` 传参；验证：MLX 后端开启纯音乐生成一首短歌，`score.abc` Vocal 全休止
- [x] 2.5 回归确认：未开纯音乐的歌曲生成流程零变化（无转谱调用、产物集合不变）

## 3. MLX style_original 二次翻译修复

- [x] 3.1 `src/yue2/style_localization.py` 新增 `resolve_style_original(style, style_original)`；`tools/mlx_generate.py localized_style` 改为调用它；验证：传入英文 style + 中文 original 时不再二次翻译，返回原文
- [x] 3.2 `tests/test_style_localization.py` 加回归用例（混合残留 CJK 的 style + 服务器原文 → 原文优先；无原文 → 正常本地化）；验证：全量 `pytest` 绿色

## 4. 校验与归档

- [x] 4.1 `openspec validate fix-instrumental-vocals --strict` 通过
- [x] 4.2 网页端实测：开纯音乐生成一首（MLX 后端），确认无人声、UI 无变化；归档变更并 `codegraph sync`
