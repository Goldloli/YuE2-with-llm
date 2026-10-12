# Proposal: fix-instrumental-vocals

## Why

用户实测 bug：高级模式开启「纯音乐」后，生成的歌曲仍带人声旋律（`outputs/2-12753`，Vocal 声部 71 个音符、39 个休止符）。

根因调查结论：

- 「纯音乐」开关仅把歌词置为 `[Instrumental]`（`web/server.py:798`、`:1009`）。`src/` 与模型目录中**没有任何**针对 `[Instrumental]` 的特殊处理——它只是歌词槽里的一段普通文本，模型是否遵循纯属概率。
- 对照样本：`dubstep-6968`（风格串含 `instrumental` 标签）Vocal 全休止、干净；`2-12753`（风格串不含该标签）泄漏人声。两个 MLX 样本结果相反，说明 `[Instrumental]` 歌词约定不可靠，而风格标签有正面作用。
- 上游官方做法（`skills/yue2-music/instrumental/`）：不依赖提示词约定，而是在规划出谱后把 Vocal 旋律**确定性地转移到 Ins 声部**再渲染，从机制上保证无人声。

附带发现的第二个 bug：`tools/mlx_generate.py` 的 `localized_style` 在服务器已提供 `--style-original` 时仍对 style 二次本地化，覆盖真实中文原文（`2-12753` 的 `style_original` 被错误改写为译文，与已修复的 `pipeline.py` 二次翻译 bug 同源）。

## What Changes

1. **风格标签强化**：`queue_song` 在 `instrumental=True` 时向 style 追加 `instrumental` 标签（大小写不敏感判重，已存在则跳过），在本地化之后追加；`style_original` 保持用户原文不变。
2. **确定性转谱（Vocal → Ins）**：凡 `instrumental=True` 且渲染输入含 ABC 谱，渲染前 MUST 执行 Vocal→Ins 转谱，复用 `skills/yue2-music/instrumental/scripts/instrumentalize.py` 的 `convert_score`：
   - 排队时已有 ABC（cover / edit 流程）：入队前直接转谱（CPU，毫秒级）。
   - torch 路径 `_generate`：`pipe.plan()` 之后，以转换谱作为固定 ABC 重建 plan 再渲染。
   - MLX 路径：`tools/mlx_generate.py` 新增 `--instrumental` 开关，同进程内 plan → 转谱 → 渲染（模型不重复加载）；`web/server.py` 按开关传参。
   - 转谱失败（谱面不规范等）：回退原谱、歌曲记录 `instrumental_warning`，**不阻塞**生成。
   - `plan_only=True`：规划阶段不转谱（用户审的是模型原谱）；后续经 cover/edit 渲染时按当时开关转谱。
3. **审计产物**：发生转谱时，输出目录保留 `score.abc`（实际渲染用的转换谱）、`score.model.abc`（模型原始谱）、`transfer.json`（转换检查报告）。
4. **修 `localized_style` 二次翻译 bug**：`--style-original` 非空时直接采信、跳过再本地化；判定逻辑下沉到 `src/yue2/style_localization.py` 供测试与复用。
5. **非目标（Non-goals）**：不改 CLI 行为（CLI 无纯音乐开关）；不改 `[Instrumental]` 歌词约定本身（保留为提示信号）；不改任何 UI 文案/视觉（本变更为纯后端/生成逻辑，无视觉差异）；不动 `models/` vendored 代码。

## Capabilities

### New Capabilities

- `instrumental-generation`: 纯音乐生成的可靠性契约——风格标签强化、Vocal→Ins 确定性转谱、失败回退与审计产物。

### Modified Capabilities

- `style-prompt-localization`: 新增需求——MLX 启动器在服务器已提供原文时 MUST 采信并跳过二次本地化。

## Impact

- **代码**：`web/server.py`（queue_song 标签强化 + 排队时转谱 + `_generate`/`_generate_mlx` 挂钩）、`tools/mlx_generate.py`（`--instrumental` + localized_style 修复）、`src/yue2/style_localization.py`（新增原文优先判定函数）。
- **复用**：`skills/yue2-music/instrumental/scripts/instrumentalize.py` 的 `convert_score`（纯函数，已有 skill 自带测试 `test_tools.py` 覆盖）。torch 在 server 进程内以 subprocess 调用其 CLI（与转录流程同模式，避免 flat import 命名冲突）；MLX 在 `mlx_generate` 子进程内 sys.path 注入导入（该进程内无同名模块）。
- **API**：无 schema 变更；歌曲记录新增可选字段 `instrumental_warning`、`transfer` 摘要。
- **测试**：标签追加与判重用例；`localized_style` 原文优先回归用例；转谱挂钩用例（含 Vocal 音符的示例谱 → Vocal 全休止；转谱失败 → 回退原谱并记 warning）；全量 `pytest` 保持绿色。
- **前端冻结合规**：不触及 `web/static/`，零视觉差异，无需视觉变更声明。
