# realaudio-tokenizer Specification

## Purpose
TBD - created by archiving change realaudio-reference. Update Purpose after archive.

## Requirements

### Requirement: 真实音频语义码提取

系统 MUST 提供真实音频 → YuE2 语义码的提取能力，流程 MUST 与社区发布方一致：24kHz 单声道 → MERT-v2-FullSong `hidden_states[20]`（30 秒分块前向）→ 线性插值到 25Hz → 逐轨 instance-norm → head v9（512 帧滑窗、argmax）→ int32 语义码序列。提取 MUST 在既有转录环境（`.venv-sheetsage2`）的子进程内完成，主环境 MUST NOT 新增依赖。输出码率 MUST 为 25 码/秒（帧数 = 时长×25 ±1）。

#### Scenario: 提取上传音频

WHEN 对 `uploads/<id>/source.*` 执行 encode
THEN 产出 `tokens.npy`（int32），长度与音频时长的 25Hz 换算一致，且结果被缓存

#### Scenario: 缓存命中

WHEN 同一音频已提取且音频文件未变
THEN 直接复用缓存，不重复运行 MERT

### Requirement: NAR LoRA 折叠与还原

渲染前系统 MUST 支持折叠 realaudio NAR LoRA：对 28 层 `nar_self_attn.{q,k,v,o}_proj` 与 `nar_mlp.{gate,up,down}_proj` 执行 `W += B@A`（scale 1.0），并以全量权重替换 `vae2llm`/`llm2vae`。折叠前 MUST 快照受影响权重，任务结束（含异常路径）MUST 还原，保证后续正常生成的模型状态与折叠前逐位一致。

#### Scenario: 折叠数学

WHEN 折叠 rank-32 LoRA 到指定线性层
THEN 权重增量为 `B@A`，与手工计算逐位一致

#### Scenario: 异常还原

WHEN 重建任务中途抛错
THEN `finally` 路径还原全部受影响权重，其后正常生成的输出与折叠前一致

### Requirement: 重建生成

系统 MUST 提供「真实音频 → 重建歌曲」路径：以 `cot="off"` 的 `SongRequest`（style/lyrics 取该音频条目元数据，缺失时为空串）构造前缀与 `SymbolicPlan`，用提取的语义码构造 `SemanticResult`，在 NAR LoRA 折叠态下 `synthesize` 并 `decode` 输出 48kHz 音频。重建 MUST 输出为新的 `kind="song"` 条目（`parent_id` 指向来源上传），且 MUST NOT 声称逐音复刻原录音。

#### Scenario: 上传条目重建

WHEN 用户对上传条目触发「YuE2 重建」
THEN 任务经 encode（或缓存）→ NAR（LoRA）→ VAE 产出新歌曲条目，可试听下载

#### Scenario: 非上传条目

WHEN 对非上传条目调用重建端点
THEN 返回 422

### Requirement: 重建的运行时边界

重建 MUST 使用 PyTorch 管线（NAR LoRA 注入仅存在于 torch 路径）；当界面选中 MLX 后端时，重建任务 MUST 仍以 torch 运行时执行并在 UI 说明。MLX 后端 MUST NOT 声称支持重建。

#### Scenario: MLX 选中时重建

WHEN 界面处于 MLX 后端且用户触发重建
THEN 任务以 torch 管线运行，按钮提示重建使用 PyTorch 运行时
