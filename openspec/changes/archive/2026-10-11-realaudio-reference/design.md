# Design: realaudio-reference

## 数据流总览

```
真实音频（uploads/source.flac 或任意文件）
   └─ .venv-sheetsage2 子进程（tools/realaudio_encode.py）
        音频 → torchaudio.load → 24kHz 单声道（resample_poly）
        → MERT-v2-FullSong（本地 models/MERT-v2-FullSong，30s 分块）
          hidden_states[20] → 帧级 [T,1024] → 线性插值 25Hz → 逐轨 instance-norm
        → head v9（Tok(1024)：Linear→512 + pos[512] + 8×TEL(d512,h8,ff2048)
          + LayerNorm + Linear→32768；512 帧窗、argmax）
        → tokens.npy（int32 @25Hz，缓存于 uploads/<id>/realaudio/）
   └─ 主环境 torch 管线（realaudio.py + 既有 pipeline）
        SongRequest(style, lyrics, cot="off") → token_prefixes → SymbolicPlan
        → SemanticResult(codec=tokens) → synthesize（NAR LoRA 折叠态）→ decode → flac
```

## 关键决策

### 决策 1：encode 跑在既有转录环境，不进主环境依赖

MERT 推理与转录栈（SheetSage2+MERT）同源，本就运行在 `.venv-sheetsage2`（torch 2.8 / transformers 4.45.2 / scipy / torchaudio），主环境缺 scipy 与音频重采样能力。采用与 `_transcribe` 相同的子进程模式（`SHEETSAGE_PY` + cwd + JSON 事件），主环境零新增依赖；head 前向同进程完成（8 层小模型，torch 版本无关紧要）。

### 决策 2：MERT 特征提取复刻官方脚本（层号/频率/归一一致）

逐项对齐 `extract_full.py` / `prep_real.py`：
- 采样率 24kHz 单声道（`resample_poly`）；
- 30s 分块（尾部不满块单独前向），`hidden_states[20]`（KEEP=[1,8,14,20] 的最后一层即 head 输入）；
- 帧率对齐：`interpolate(size=round(秒数×25), linear)` → 25Hz；
- **逐轨 instance-norm**（训练同款：均值/标准差按时间轴，逐轨独立）——head 的域适配关键，漏掉会显著掉点。

### 决策 3：head 载入与推理

- safetensors 直读（`ckpt_io.py` 的 `.pt` 分支不需要；只支持 .safetensors 发布物）；
- 架构常量：`D=512, L=8, H=8, FFN=2048, VOCAB=32768, WIN=512`（取自发布训练脚本）；
- 推理：整段特征**滑窗 512 帧、步长 512**（非重叠，尾窗右侧 pad 后裁齐），argmax 取码——与训练窗口一致且无需 soft 目标表（`sem_nbr_*` 仅训练用，下载但暂不消费）；
- 输出 dtype int32，便于 .npy 缓存与后续训练消费。

### 决策 4：NAR LoRA 折叠 + 快照还原

- 折叠：解析 `layers.{i}.nar_self_attn.{q,k,v,o}_proj.lora_{A,B}`、`layers.{i}.nar_mlp.{gate,up,down}_proj.lora_{A,B}` → `W += B@A`（scale 1.0，无 alpha）；`vae2llm`/`llm2vae` 为**全量替换权重**（非 delta）；
- 还原：折叠前对 28 层受影响 Linear 与两个桥接层做 `weight.detach().clone()` 快照（总计 <500MB 量级 fp32？实际为模型权重切片，避免整模型复制；受影响参数量按 rank-32 LoRA 覆盖的线性层——约 2-3GB fp16，实施时按实际评估内存），任务结束（成功或异常，`finally`）还原；
- 选择快照还原而非整模型重载：重载 3B 模型在 MPS 上约 1-2 分钟，快照还原毫秒级；快照占用可控。

### 决策 5：rebuild 任务的产物语义

- 产物是**新的 `kind="song"` 条目**（不是替换上传条目），`parent_id=上传 id`，`cot="off"`（无新谱）——可试听、可下载、可对二次操作（cover/edit 需要谱，不适用，符合「重建无谱」的事实）；
- 歌曲记录带 `realaudio: {frames, seconds}` 摘要；详情面板技术信息加一行「语义帧 N @25Hz」；
- 重建使用原上传曲目的 style/lyrics 元数据（转录产物已有歌词/风格则用之；否则 style="", lyrics="」的最小前缀，记录在 request.json 并可复现）。

### 决策 6：与 decoder 设置的交互

重建的 VAE 解码 MUST 遵循当前 `decoder` 设置（default/legacy/merge——merge 档来自 settings-menu-overhaul 提案）——用户选的音色档位对所有 torch 渲染路径（含重建）一致生效。若 merge 未安装则回退 default。

### 决策 7：失败面与缓存

- encode 失败（无 source 音频/MERT 异常）：任务报错，不产生半成品；
- tokens 缓存：`uploads/<id>/realaudio/tokens.npy` 存在且音频 mtime 未变则跳过 encode（重试、重复重建零成本）；
- rebuild 在 MLX 后端选择下：任务照走 torch 管线（按钮 tooltip 明确「重建使用 PyTorch 运行时」）。

## 风险与缓解

- **重建保真**：非逐比特复刻；验证以「时长匹配、可听、无人为噪声」为准，不承诺与原音逐音一致（proposal 已声明社区 ~95% 听测口径）。
- **长曲内存**：25Hz × 10 分钟 = 15k 帧特征（15k×1024 fp16 ≈ 30MB）可控；MERT 30s 分块前向避免峰值。
- **主环境 torch 2.10 与 head**：head 只在 sheetsage2 环境前向，主环境仅做 LoRA 折叠（纯张量）——版本差异不影响。
- **encode 与常驻模型的共存内存**：encode 在独立进程（sheetsage2 环境，MERT 约数 GB）；若主管线此刻常驻（3B 模型在 MPS），两进程峰值叠加。缓解：rebuild 任务在 runner 单 worker 内串行（encode 完成后才进入管线渲染），且 encode 可先于模型加载；实测记录峰值内存，超限时提示用户先在空闲时运行。
