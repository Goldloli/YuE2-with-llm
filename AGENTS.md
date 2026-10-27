# AGENTS.md

本文件是 AI 编码助手在本仓库工作时的约定。**任何改动的第一优先级规则见「改动工作流」一节。**

## 项目概述

YuE2 推理仓库（`yue2-infer` 0.1.6）：一个音乐生成项目，输入歌词（lyrics）+ 风格提示词（style/tags），先由 3B 语言模型写出旋律与和弦的符号化计划（ABC notation），再经 VAE/声码器合成完整歌曲（人声 + 伴奏）。

- 核心代码：`src/yue2/`（pipeline、protocol、tokenizer、模型、采样等）
- 入口：`yue2` CLI（`src/yue2/cli.py`）、Web 服务（`web/server.py`）、MLX 端口（`tools/mlx_generate.py`、`models/YuE2-3B-MLX/`）
- 请求样例：`requests/`、`examples/song.json`
- 配套 skill：`skills/yue2-music/`
- Python ≥ 3.10，pytest 测试在 `tests/`

## 常用命令

```bash
# 测试（全部）
pytest
# 单个测试文件
pytest tests/test_protocol.py

# CLI 生成
yue2 generate --style "..." --lyrics-file ... 

# Web 服务
python web/server.py
```

## 改动工作流（强制）

**所有代码/功能改动必须先写 OpenSpec 提案文档，经用户确认后才可实施。** 顺序不可颠倒：

1. **提案**：使用 openspec-propose 流程创建变更（`openspec new change <kebab-case-name>`），生成 `proposal.md`、`design.md`、`tasks.md`、`specs/` delta 等全部规划产物。
2. **等待确认**：提案完成后停下来，向用户展示产物并等待明确确认。**未获确认前不得修改任何项目代码。**
3. **实施**：用户确认后，走 openspec-apply-change 流程按 `tasks.md` 实施。
4. **归档**：实施完成并验证后，走 openspec-archive-change 流程归档。

例外：拼写错误、注释/文档 typo 这类不改变行为的单行修复可直接改；如有疑问，仍走提案流程。

## OpenSpec

- 已在本仓库初始化（OpenSpec CLI 1.12.0），配置：`openspec/config.yaml`（schema: `spec-driven`）。
- **所有 OpenSpec 产物用中文书写**（结构性标题和 SHALL/MUST 关键字保留英文）。
- 目录：`openspec/changes/`（进行中的变更）、`openspec/specs/`（已归档能力规格）、`openspec/changes/archive/`。
- 常用命令：`openspec status --change <name>`、`openspec validate <name>`、`openspec list`。

## CodeGraph

本仓库已初始化 CodeGraph 代码索引（`.codegraph/codegraph.db`，索引 179 个文件）。查代码时优先用它而不是全库 grep：

```bash
codegraph query <符号名>      # 搜符号
codegraph explore <主题>      # 相关符号源码 + 调用路径
codegraph node <名称>         # 单个符号源码 + 调用方/被调方
codegraph sync                # 改动后同步索引
```

## 前端风格冻结

`web/static/` 是已冻结的暗色三栏音乐工作台视觉基线（参考主流 AI 音乐产品风格），**视觉风格已冻结**，契约见 `openspec/specs/web-ui-design/spec.md`（冻结基线）。任何触及 `web/static/` 的提案必须对照该规格自查；改变外观/布局/组件视觉/品牌元素的提案必须在 proposal 中显式声明「视觉变更」并经用户确认。设计令牌以 `styles.css` `:root` 为唯一来源，新增样式必须复用令牌；纯文案/i18n、不可见行为修复不算视觉变更。基线截图在 `docs/ui-baseline/`。

## 提示词现状

- `style`/`tags`：模型按英文逗号分隔标签训练（如 `"Mandarin, warm piano, acoustic pop, female vocal"`）。
- 中文 style 支持已实现（`src/yue2/style_localization.py`）：`auto` 模式（默认）检测到 CJK 字符时，在请求构建与身份哈希之前把 style 翻译成英文标签——优先 `YUE2_STYLE_LLM_BASE_URL`/`YUE2_STYLE_LLM_API_KEY`/`YUE2_STYLE_LLM_MODEL` 配置的 OpenAI 兼容端点（超时 ≤10s），失败回退内置词典 `src/yue2/data/zh_style_terms.json`（未命中词保留原文），全部不可用时原样透传并告警（Web 响应带 `style_warning`）。`--style-language en|off` 完全跳过检测与翻译。
- 持久化：`request.json` 中 `style` 为翻译后的英文，`style_original` 为中文原文（仅在发生翻译时存在）；重跑已持久化请求不会重复翻译。
- `lyrics`：天然支持中文歌词（byte-level BPE，无 OOV），不做任何检测/翻译。

## Git 约定

- 主分支 `main`，跟踪 `origin/main`。
- 提交前确保 `pytest` 通过。
- 不要提交 `outputs/`、`models/` 等产物（已在 `.gitignore`）；`.codegraph/` 索引 likewise 已忽略。
