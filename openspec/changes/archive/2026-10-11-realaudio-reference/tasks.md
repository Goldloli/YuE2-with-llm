# Tasks: realaudio-reference

## 1. 资产与提取

- [x] 1.1 `tools/download_extras.sh` + `tools/hf_download.py`：新增 `Mothersuperior/yue2-mothersuperior-realaudio-tokenizer-v4` 的 `tokenizer_head_joint_v9.bf16.safetensors`、`nar_lora_joint_v9.bf16.safetensors`、`assets/sem_nbr_idx.npy`、`assets/sem_nbr_cos.npy` → `models/YuE2-Realaudio/`；执行下载并核对 sha 大小
- [x] 1.2 `tools/realaudio_encode.py`（.venv-sheetsage2 运行）：音频 → 24k 单声道 → MERT L20 @25Hz + 逐轨 instance-norm → head v9 滑窗 argmax → tokens.npy；验证：对 `uploads/song-6222/source.flac` 运行，帧数 ≈ 时长×25，无 NaN
- [x] 1.3 单测：head 架构载入（103 张量、形状）、滑窗切分含尾窗 pad、instance-norm 数值正确性

## 2. NAR LoRA 与管线能力

- [x] 2.1 `src/yue2/realaudio.py`：`load_nar_lora` / `merge_nar_lora`（28 层 delta 折叠 + vae2llm/llm2vae 替换）/ `snapshot_weights` / `restore_weights`；验证：折叠后权重与 `B@A` 手算一致，还原后与原权重逐位相等
- [x] 2.2 重建路径：`SongRequest(cot="off")` + `token_prefixes` → `SymbolicPlan` → `SemanticResult(codec=tokens)` → `synthesize` → `decode` 封装为 `rebuild(pipe, tokens, style, lyrics)`；验证：用 1.2 的 tokens 重建 10 秒片段，音频时长≈ tokens/25 秒且无异常
- [x] 2.3 `finally` 还原：重建任务异常抛出后常驻模型权重与任务前一致；验证：注入异常后跑一首正常生成对比输出与未折叠态一致

## 3. CLI 与 Web 集成

- [x] 3.1 `tools/realaudio.py`：`encode` / `rebuild` 两条子命令（含 `--nar-lora` 默认取 `models/YuE2-Realaudio/`）；验证：命令行完成一次上传音频的 encode+rebuild，产出 flac
- [x] 3.2 `web/server.py`：任务 kind `rebuild`（torch 管线；encode 走 SHEETSAGE_PY 子进程 + tokens 缓存；产物新 song 条目 + `realaudio` 摘要）；端点 `POST /api/songs/{id}/rebuild`（仅上传条目）
- [x] 3.3 `web/static/app.js` + `i18n.js`：上传条目详情面板加「YuE2 重建」按钮（复用 `.dact` 模式）；技术信息加「语义帧」行；验证：按钮触发任务、进度可见、产物出现在列表
- [x] 3.4 服务端测试：rebuild 端点对非上传条目 422；tokens 缓存命中不重复 encode
- [x] 3.5 文档 `docs/realaudio.md`：encode/rebuild 用法、v9 联合对说明、AR LoRA 训练指引（外部 CUDA 流程 + tokens.npy 作为语料接口）、保真口径（非逐音复刻）声明

## 4. 实测

- [x] 4.1 上传音频 → 重建完整流程实测（真机 MPS）：encode 耗时、rebuild 耗时、产物时长与听感检查（不承诺逐音一致）
- [x] 4.2 重建后跑一首正常生成，确认模型权重还原无副作用；全量 `pytest` 绿色

## 5. 校验与归档

- [x] 5.1 `openspec validate realaudio-reference --strict`；归档；`codegraph sync`
