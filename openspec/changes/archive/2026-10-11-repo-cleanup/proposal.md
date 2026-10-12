# Proposal: repo-cleanup

## Why

项目经多轮会话开发后，根目录与各处积累了一批可再生缓存、会话追踪文件和一次性测试产物；另有三类文件放错了位置。用户要求彻底清理「杂七杂八没用的东西」。本提案先给出完整处置清单（分「删除 / 归位 / 保留」三档），避免误伤。

## What Changes

### A. 删除（可再生或一次性，均已逐项核实）

1. `.playwright-mcp/`——180 个会话浏览器快照/日志（3.0 MB），工具生成，可随时再生；
2. `.pytest_cache/`、全部 `__pycache__/`（7 处）、`.DS_Store`（1 处）、空的 `.cache/`——缓存类，可再生；
3. `src/yue2_infer.egg-info/`——pip 构建中间产物，`pip install -e` 会再生；
4. `outputs/comparisons/`（7.3 MB 孤儿对比渲染）、`outputs/zh-style-test/`（7.2 MB 孤儿 CLI 测试产物）——不在 library 中的一次性生成物；
5. library 孤儿记录 `brutal-test-2-lora-790`（failed、磁盘无目录的测试条目）——从 `web/data/library.json` 删除。

### B. 归位（移动，不删除）

6. 根目录 `ref-suno-home.png`、`ref-suno-signin.png` → `ref-suno/`（参考图归入参考目录）；
7. `requests/ink_moonlight.json` → `examples/ink_moonlight.json`（这是一个完整可用的示例请求，散落的 `requests/` 目录取消）；
8. `START.md` → `packaging/使用说明.md`（与 oneclick-packaging 变更联动，见该提案）。

### C. 明确保留（附不删理由，防止误伤）

- `compare/`（11 MB 开发期人工对照截图，冻结规格将其记录为既有工作方式）、`ref-suno/`（15 MB Suno 参考图，冻结基线等归档提案引用）；
- `outputs/` 中 library 内的全部歌曲、`web/data/`（用户数据与上传）、`models/`（全部权重）、`.kimi-code/`（openspec 技能文件，工作流依赖）、`.codegraph/`（索引）、`.venv*`。

### D. 根目录卫生规则（新增到 repository-hygiene 规格）

清理后确立并写入规格，防止再积累：产物/缓存类文件不得留在根目录；缓存目录必须进 `.gitignore`（`.playwright-mcp/` 本次补漏）。

非目标（Non-goals）：不删除任何 library 内歌曲与其产物；不动 `compare/`、`ref-suno/`（用户如要删说一声即可）；不做 git 历史操作（提交由用户决定）。

## Capabilities

### New Capabilities

- `repository-hygiene`: 仓库根目录与缓存卫生的长期规则（可再生文件处置、gitignore 覆盖、禁止根目录堆积）。

### Modified Capabilities

（无）

## Impact

- **删除量**：约 17.5 MB 可再生/一次性文件 + 1 条孤儿库记录；`docs/realaudio.md` 等真实文档不受影响。
- **`.gitignore`**：补 `.playwright-mcp/`（其余缓存已在）。
- **风险**：低。所有删除项均为可再生产物或经核实的一次性测试文件；对照截图与参考图明确保留。
