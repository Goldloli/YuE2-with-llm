# Spec Delta: instrumental-generation（新能力）

## ADDED Requirements

### Requirement: 纯音乐风格标签强化

当歌曲以 `instrumental=True` 入队时，系统 MUST 确保最终使用的风格标签串包含 `instrumental` 标签（大小写不敏感判重，已存在则不变）。标签追加 MUST 发生在风格本地化之后，且 MUST NOT 修改 `style_original`（用户原始输入）。

#### Scenario: 中文风格 + 纯音乐

WHEN 用户以中文风格（如「中国风，电子乐」）开启纯音乐创建歌曲
THEN 入队歌曲的 `style` 为翻译后的英文标签并含 `instrumental`，`style_original` 仍为中文原文

#### Scenario: 风格已含 instrumental

WHEN 用户风格文本翻译后已包含 `instrumental`（任意大小写）
THEN `style` 不重复追加

### Requirement: 人声旋律确定性转移

凡 `instrumental=True` 且渲染输入包含 ABC 谱（新建规划产出或 cover/edit 提供），系统 MUST 在渲染前对谱面执行 Vocal→Ins 转移：Vocal 声部的全部音符（音高、起音、时值）移入 Ins 声部，Vocal 仅保留休止符与和弦标记；与 Vocal 重叠的 Ins 原音符按 Vocal 优先缩编。转移 MUST 逐音符校验（音高/时值/拍号/速度/和弦），校验失败视为转移失败。

#### Scenario: 新建纯音乐（torch 或 MLX）

WHEN 用户开启纯音乐新建歌曲，规划产出的谱面 Vocal 声部含音符
THEN 渲染所用的 `score.abc` 中 Vocal 声部不含任何音符，Vocal 原旋律完整出现在 Ins 声部

#### Scenario: 纯音乐 cover

WHEN 用户对含人声旋律的歌曲发起纯音乐 cover
THEN 入队的条件谱已完成 Vocal→Ins 转移，渲染结果不含人声旋律

#### Scenario: 谱面无 Vocal 音符

WHEN 待渲染谱面的 Vocal 声部本就只有休止符
THEN 转移退化为 no-op，流程继续且不产生额外审计文件

### Requirement: 转移失败回退

谱面不规范等原因导致转移失败时，系统 MUST 回退为使用原谱继续渲染，并在歌曲记录中写入 `instrumental_warning`（含错误摘要）；转移失败 MUST NOT 阻塞或失败整首生成。

#### Scenario: 不规范谱面

WHEN 转移函数对输入谱抛出校验错误
THEN 生成以原谱继续，歌曲记录含 `instrumental_warning` 字段

### Requirement: 转移审计产物

发生 Vocal→Ins 转移时，输出目录 MUST 保留：`score.abc`（实际渲染用的转换谱）、`score.model.abc`（转移前的模型原谱或输入原谱）、`transfer.json`（转移检查报告，含音符计数与重叠缩编明细）。未发生转移时 MUST NOT 产生这两个额外文件。

#### Scenario: 检查渲染输入谱

WHEN 一首纯音乐歌曲生成完成且发生过转移
THEN 输出目录同时存在 `score.abc`（Vocal 全休止）与 `score.model.abc`（含 Vocal 原旋律），`transfer.json` 记录 `vocal_notes_after == 0`

### Requirement: 先审后烧语义

`plan_only=True` 的纯音乐歌曲在规划阶段 MUST NOT 转移声部（用户审阅的是模型原始谱）；后续经 cover/edit 流程渲染时，按渲染请求当时的 `instrumental` 开关执行转移。

#### Scenario: 审谱后渲染

WHEN 纯音乐 plan_only 歌曲的谱面被用户确认并发起渲染
THEN 渲染输入谱在渲染前完成 Vocal→Ins 转移
