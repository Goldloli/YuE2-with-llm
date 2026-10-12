# Design: support-chinese-style-prompts

## Context

现状关键事实（依据代码调研，见 proposal.md）：

- style 是纯透传字符串，唯一组装点 `SongRequest.text()`（`src/yue2/protocol.py:108`），模板为 `{instruction}\n[Tags]\n{style}\n[Lyrics]\n{lyrics}\n`。
- 入口三处：CLI `request_kwargs`（`src/yue2/cli.py:40`）、Web `queue_from_request`（`web/server.py:741`）、MLX 子进程（`tools/mlx_generate.py:121`，模板在 `models/YuE2-3B-MLX/generate.py:75` 重复实现）。
- 请求身份哈希在 `pipeline.__call__`（`src/yue2/pipeline.py:382`），基于最终请求字段。
- 分词器为 byte-level BPE，中文无 OOV；瓶颈是 checkpoint 训练分布（英文 `[Tags]`），不是编码。
- CFG 负向分支自动派生（instruction + ABC，不含 tags/lyrics），不受本变更影响。

## Goals / Non-Goals

**Goals:**

- 中文 style 经翻译后以英文标签形态进入 `[Tags]` 块，模型侧零改动。
- 翻译在身份哈希之前完成并随 `request.json` 持久化，运行可复现、翻译结果可审查。
- 三条入口（CLI / Web / MLX）共用同一实现，无分叉。

**Non-Goals:**

- 不改 lyrics、不改模板/协议版本、不改模型权重。
- 不引入强制第三方依赖（langdetect、翻译 SDK 等）；LLM 端点走标准 HTTP，可选。
- 不做双语 `[Tags]` 直推或中文标签微调（后续提案，需质量基准）。

## Decisions

### D1: 翻译-first，而非让模型直接收中文

checkpoint 的 `yue2-native-v1` 协议按英文 instruction + 英文 `[Tags]` 训练；中文标签属分布外输入，跟随质量不可控。翻译-first 保持模型输入分布不变，是唯一不需要质量回归基准即可上线的路线。

备选：双语 `[Tags]` 混排——偏离 checkpoint 原生协议，需单独基准验证，否决（留作后续）。

### D2: 单一汇聚函数，而非各入口分别处理

新增 `src/yue2/style_localization.py`，暴露 `localize_style(style, mode, provider_chain) -> (final_style, style_original, translated: bool)`。CLI `request_kwargs`、Web `queue_from_request`、MLX `mlx_generate.py` 在构建 SongRequest 之前统一调用。Web 嗓音后缀改为在 `queue_from_request` 内、翻译之后追加（从 `app.js` 前端拼接改为后端拼接，前端只传 `vocal_gender` 字段）。

备选：前端继续拼接——中文文本会先被拼上英文后缀再翻译，污染翻译输入，否决。

### D3: 提供者链：LLM 端点 → 内置词典 → 透传告警

- **LLM 提供者**：OpenAI 兼容 chat completions 端点，由环境变量/配置文件指定（`YUE2_STYLE_LLM_BASE_URL` / `YUE2_STYLE_LLM_API_KEY` / `YUE2_STYLE_LLM_MODEL`）；提示词约束输出为英文逗号分隔标签。超时/错误即降级。
- **词典提供者**：纯数据文件（`src/yue2/data/zh_style_terms.json` 或同包 yaml），覆盖常见流派、乐器、情绪、嗓音、速度术语；整句输入按词典切片翻译，未命中词保留原文。无网络、零依赖，保证离线可用。
- **透传**：记录 warning，Web 响应中带 `style_warning` 字段。

备选：引入 `langdetect`/翻译 API SDK——硬依赖与离线目标冲突，否决。

### D4: 检测用 Unicode 区间，不引入语言检测库

`[\u4e00-\u9fff\u3400-\u4dbf]` 出现即判中文。音乐 style 是短标签文本，语言检测库在此粒度上收益低、依赖不值得。

### D5: 持久化双字段 + 哈希边界

`localize_style` 在 `pipeline.__call__` 的哈希计算之前调用；`request.json` 写入 `style`（英文）与 `style_original`（中文原文）。重复运行已持久化请求时跳过翻译（检测到已是英文，自然幂等）。

### D6: 默认 `auto`

`auto` 对纯英文输入零行为变化（检测为英文即短路，见 spec「纯英文 style」场景），因此默认开启安全。`off` 提供一键回滚到当前版本行为。

## Risks / Trade-offs

- [LLM 翻译质量波动，术语译法不统一] → 词典提供者按术语表保真优先；`request.json` 持久化使每次翻译结果可审查、可复现。
- [LLM 端点不可达导致延迟/失败] → 短超时（默认 ≤10s）+ 自动降级词典，生成不中断。
- [中英混排被误判需要翻译] → 翻译提示词明确要求保留已有英文标签；spec 场景固定该行为。
- [词典覆盖率有限，生僻描述译不准] → 未命中词保留原文附后，模型对少量中文残留有 tokenizer 层面的容忍；告警提示用户改用英文或配置 LLM。
- [默认 `auto` 改变中文输入的既有行为] → 这正是本变更的目的；`--style-language off` 可完全回退。

## Migration Plan

- 存量英文请求文件（`requests/`、`examples/song.json`）不受影响。
- 存量中文 style 的 Web 使用从「原样透传」变为「翻译后生成」——行为改善，无需数据迁移。
- 回滚：CLI/Web 设置 `--style-language off`；代码层面删除汇聚调用即可完全还原。

## Open Questions

- 内置词典的初始术语规模（首版约 200 条常见流派/乐器/情绪/嗓音词条）——可在实施时按 `docs/benchmarks.md` 中出现过的风格词收敛，不影响规格与任务拆分。
