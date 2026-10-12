# Proposal: realaudio-reference

## Why

YuE2 官方不带「真实音频 → 语义 token」编码器，社区（Mothersuperior）补齐了这一环：[yue2-mothersuperior-realaudio-tokenizer-v4](https://hf-mirror.com/Mothersuperior/yue2-mothersuperior-realaudio-tokenizer-v4) 发布了 MERT→语义码 tokenizer head（v9/v8/v5 联合对）+ NAR 解码 LoRA——把任意真实录音 tokenize 后经 YuE2 的 NAR+VAE 重渲染（社区听测重建保真 ~95%），并可作为后续 AR LoRA 风格训练的语料入口。用户要求把该能力接进本项目。

**本机（Apple Silicon）可行性已逐项核实**：MERT-v2-FullSong 权重本地已有（转录栈在用）；head 为 8 层 d=512 小模型（架构在发布脚本中完整公开）；NAR LoRA 折叠是纯张量运算；全套可在本机跑通，无需 CUDA。

## What Changes

**本提案包含一处小型视觉变更（按 `web-ui-design` 规格显式声明）**：上传条目详情面板新增「YuE2 重建」按钮（复用既有 `.dact` 按钮模式与图标语言，无新组件形态、不改布局与令牌）；其余部分为后端/管线变更，零视觉影响。现有基线取景为歌曲条目（不含该按钮），`docs/ui-baseline/` 无需更新；实施后人工核查既有页面无意外差异。

1. **资产获取**：`tools/download_extras.sh` + `tools/hf_download.py` 增加 `Mothersuperior/yue2-mothersuperior-realaudio-tokenizer-v4`（hf-mirror）的 v9 联合对与依赖表：`tokenizer_head_joint_v9.bf16.safetensors`、`nar_lora_joint_v9.bf16.safetensors`、`assets/sem_nbr_idx.npy`、`assets/sem_nbr_cos.npy` → `models/YuE2-Realaudio/`；
2. **语义码提取**（新 CLI + 编码脚本，运行于既有 `.venv-sheetsage2` 转录环境，子进程模式与转录一致）：
   - `tools/realaudio_encode.py`：音频 →（torchaudio 载入/重采样 24kHz 单声道）→ MERT-v2-FullSong layer-20 特征（30s 分块、线性插值到 25Hz、逐轨 instance-norm）→ head（滑动 512 帧窗 argmax）→ `tokens.npy`（int32，25 Hz 语义码）；
3. **NAR LoRA 支持**（`src/yue2` 新增 `realaudio.py`）：
   - `merge_nar_lora(model, path)`：对 28 层 `nar_self_attn.{q,k,v,o}_proj` + `nar_mlp.{gate,up,down}_proj` 折叠 `W += B@A`（scale 1.0），并全量替换 `vae2llm`/`llm2vae`；
   - `snapshot_weights(model)` / `restore_weights(model, snap)`：折叠前快照受影响权重，任务结束还原——避免污染常驻模型的后续正常生成（不重载全模型）；
4. **重建生成**（管线的既有能力组合，无新采样逻辑）：`SongRequest(style=原曲风格, lyrics=原曲歌词, cot="off")` → `token_prefixes` 构造前缀 → `SymbolicPlan` + `SemanticResult(codec=tokens)` → `synthesize`（NAR LoRA 折叠态）→ `decode`；
5. **CLI `tools/realaudio.py`**：`encode <audio> -o tokens.npy`；`rebuild <audio> -o out.flac [--nar-lora …]`（encode → 重建 → 保存 flac + 统计）；
6. **Web 集成**：上传条目的详情面板新增「YuE2 重建」按钮 → 新任务类型 `rebuild`（torch 后端）——读 `uploads/<id>/source.*` → encode（子进程，缓存在 `uploads/<id>/realaudio/tokens.npy`）→ 重建 → 产物落为新的 `kind="song"` 条目（`parent_id` 指向上传 id），库中可试听/同其他歌曲操作；MLX 后端不支持重建（NAR LoRA 注入仅 torch 路径），按钮在 MLX 选中时仍可用但强制走 torch；
7. **非目标（Non-goals）**：
   - **不做 AR LoRA 训练**（用自己歌单训风格 LoRA）：其官方流程依赖 CUDA pod、demucs 人声分离与 MMS 强制对齐，Apple Silicon 上不可行；仅在文档中给出指引与数据准备接口（tokens.npy 即训练语料入口）；
   - 不引入 v8/v5/v4 旧版 head/LoRA（只做 v9 联合对）；不接入 ComfyUI 布局的 `_comfyui` 文件；
   - 不改 cover/编辑/转录既有路径的语义；不做 MLX 版 rebuild。

## Capabilities

### New Capabilities

- `realaudio-tokenizer`: 真实音频 →（MERT+head）语义码 →（NAR+LoRA）重建的完整契约：提取正确性（25Hz、逐轨归一）、LoRA 折叠与还原、失败回退、CLI 与任务接口。

### Modified Capabilities

（无——不触及既有 spec 的行为；Web 按钮沿用其所属面板的既有组件）

## Impact

- **代码**：`tools/download_extras.sh` / `tools/hf_download.py`（资产）、`tools/realaudio_encode.py`（新，sheetsage2 环境）、`tools/realaudio.py`（新 CLI）、`src/yue2/realaudio.py`（新：head 载入/折叠/快照）、`web/server.py`（rebuild 任务 kind + 端点）、`web/static/app.js`（详情面板按钮）+ `i18n.js`（1–2 条文案）。
- **依赖**：无新增（sheetsage2 环境已有 torch/transformers/scipy/torchaudio；主环境仅用 torch/safetensors/numpy）。
- **数据**：`models/YuE2-Realaudio/`（head ~200MB + LoRA ~200MB 级）；上传目录新增 `realaudio/tokens.npy` 缓存。
- **测试**：`src/yue2/realaudio.py` 的折叠/还原数学与 head 前向形状单测；`pytest` 全量绿色；上传一首真实音频实测 encode（帧数=时长×25）与 rebuild（时长匹配、可试听）。
- **文档**：新增 `docs/realaudio.md`（encode/rebuild 用法、v9 联合对说明、AR LoRA 训练的指引与数据准备接口、保真口径声明）。
- **基线**：无基线变更——重建按钮位于上传条目详情面板，现有基线取景为歌曲条目；实施后按冻结规则人工核查该按钮不引起既有页面差异。
- **风险**：重建≠原音复刻（社区数据 top-1 语义码命中 ~19%，但近邻码听感差异小、整体听测 ~95%）；head 为逐帧独立打分，长曲推理内存需分窗流式（实施时按 512 帧滑窗分块）；MERT 在全曲长度上的耗时（分钟级）——encode 结果缓存避免重复。
