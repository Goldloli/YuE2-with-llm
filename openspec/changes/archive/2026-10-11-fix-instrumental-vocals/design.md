# Design: fix-instrumental-vocals

## 证据表（bug 定性依据）

| 输出 | 后端 | cot | 风格串含 instrumental | Vocal 声部 | 结论 |
|---|---|---|---|---|---|
| `dubstep-6968` | mlx | full | 是 | 0 音符 / 128 休止 | 干净 |
| `ai-0o-cover-5933` | mlx | melody(cover) | 否 | 0 音符 / 38 休止 | 干净 |
| `ai-0o-cover-97` | torch | full | 否 | 0 音符 / 38 休止 | 干净 |
| `2-12753` | mlx | full | 否 | **71 音符** / 39 休止 | 泄漏人声 |

prompt 模板（`INSTRUCTIONS`/`[Tags]`/`[Lyrics]`）在 torch 与 MLX 路径逐字一致，已排除模板差异。`[Instrumental]` 仅是歌词槽文本，无机制强制；风格串含 `instrumental` 标签的样本全部干净。上游 skill 的官方纯音乐工作流（Vocal→Ins 转谱）是确定性方案。

## 关键决策

### 决策 1：双保险而非单一手段

- **提示层**（风格标签追加 `instrumental`）：让规划器写出本就适合纯音乐的谱（前奏/间奏结构、无歌词段落倾向），但不能保证 Vocal 声部无音符。
- **机制层**（Vocal→Ins 转谱）：确定性保证渲染输入的 Vocal 声部只有休止符与和弦标记。
- 只做提示层：bug 仍会偶发（本 bug 即为证据）。只做机制层：可行，但模型规划时仍按「有歌词」组织曲式，音乐性略差。两者叠加是上游 skill 的既定做法。

### 决策 2：转谱复用 skill 实现，不做代码移植

`convert_score(text, *, overlap='vocal', keep_chords=True)` 是纯函数（输入 ABC 文本，输出 `(转换谱, 检查报告)`），内部已完成音符级校验（音高/时值/拍号/速度/和弦逐一对账，不一致即抛错）。移植进 `src/yue2/` 会产生约 700 行的双份维护；skill 脚本随仓库发布且有 `test_tools.py` 覆盖。

导入方式按进程隔离现状选择：

- **torch（web/server.py 进程）**：subprocess 调用 `instrumentalize.py` CLI（`python instrumentalize.py <abc> --output <dir>`），与现有 SheetSage2 转录的 subprocess 模式一致；避免 `abc_tools`/`compile_score` 等 flat 模块名污染 server 进程命名空间（`skills/yue2-music/scripts/` 与 `skills/yue2-music/instrumental/scripts/` 下存在同名 `abc_tools.py`）。
- **MLX（tools/mlx_generate.py 子进程）**：该进程内仅 `generate.py` 一个外来模块，sys.path 注入 `instrumental/scripts` 后 `import instrumentalize` 无冲突；同进程完成 plan→转谱→渲染，避免 MLX 模型二次加载（每次加载数十秒）。

### 决策 3：转谱失败回退而非报错

`convert_score` 对不规范谱面会抛 `ValueError`（如 Vocal/Ins 均无音符、未知段落标签、小节内变音）。纯音乐是用户明确意图，但谱面问题不应让整首生成失败：回退原谱继续渲染，歌曲记录写 `instrumental_warning`（含错误摘要），UI 无需改动（详情接口已透传歌曲字段）。

### 决策 4：转谱挂钩点

- **入队已有 ABC**（cover/edit）：`queue_song` 内、本地化之后执行，转换谱作为 `abc` 入队。父歌曲的原谱仍在父目录，天然保留。
- **新建（torch）**：`_generate` 中 `pipe.plan()` 返回后，若 `plan.abc` 的 Vocal 有声符则转谱，`dataclasses.replace(request, abc=converted)` 重建 `pipe.plan(request=...)`（外部 ABC 路径只做分词与前缀校验，无模型调用，开销可忽略）。
- **新建（MLX）**：`tools/mlx_generate.py --instrumental` 内部完成。`--plan-only` 与 `--instrumental` 同传时规划后仍只出谱（不转谱），与决策的 plan_only 语义一致。
- **plan_only 后续渲染**：用户审谱后经 cover/edit 渲染，走「入队已有 ABC」分支。

### 决策 5：产物命名

输出目录 `score.abc` 始终是**实际用于渲染的谱**（语义不变，前端 `current_score` 等读取不受影响）；发生转谱时额外写 `score.model.abc`（模型原谱）与 `transfer.json`（`convert_score` 的检查报告）。未发生转谱（无 Vocal 音符、转谱回退）时不写这两个文件。

### 决策 6：`localized_style` 修复下沉

`src/yue2/style_localization.py` 新增 `resolve_style_original(style, style_original)`：原文非空时返回 `(style, style_original if style_original != style else None)`，否则返回 `localize_style` 结果。`tools/mlx_generate.py` 改为调用它。与 `pipeline.py:226-238` 的「上游已提供原文则跳过翻译」语义对齐，测试直接打在 src 层。

## 风险与缓解

- **转谱改变音乐结构**：Vocal 音符并入 Ins 后，Ins 从「伴奏填充」变成「主旋律+填充」。这正是上游纯音乐工作流的定义行为；`transfer.json` 保留逐音符对账。
- **MLX 8bit 遵循度**：转谱后 Vocal 全休止，模型只剩「按谱渲染」，无自由发挥空间，风险消除。
- **cover 源谱本就无 Vocal 音符**：`convert_score` 退化为近 no-op（Vocal 空 → merged=Ins 原音符），安全。
