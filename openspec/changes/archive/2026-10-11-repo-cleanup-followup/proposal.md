# Proposal: repo-cleanup-followup

## Why

上轮清理后做了一次深度扫描（全目录体积排行、缓存再生检查、引用完整性核对），定位出最后一批「没用的东西」：`compare/` 目录里 66 个一次性迭代/验证截图（11 MB，全部未入 git）、一个基准测试中间产物、以及测试运行后再生长的字节码缓存。用户要求项目再干净一些。

## What Changes

### A. 删除

1. **`compare/` 整个目录（66 个文件，11 MB）**——全部是一次性产物：
   - `round01–round30-*`（29 张）：「Suno 像素级复刻」开发过程的逐轮迭代截图，最终形态已冻结在 `docs/ui-baseline/`；
   - `i18n-*`、`extras-*`、`extras2-*`、`model-pill-*`、`mlx-*`、`final-*`、`cross-settings-perf.png`、`ref-createsimple-2560.png`、`cover-model-*`（35 张）：历史变更的验证截图，对应提案已归档（描述在档，证据使命完成）；
   - `cover-options.html/.png`（2 个）：封面方案 A–D 对比 demo，仅被归档提案引用；删除后该引用成为历史记录（归档提案正文仍完整描述方案与结论）。
2. **`outputs/bench-torch.json`**——速度基准测试的中间产物（非曲库数据），删除。
3. **再生长的 `__pycache__/`（6 处、48 个 `.pyc`）**——统一在收尾时清除（测试/运行会再生，已被 `.gitignore` 覆盖，不影响 git）。

### B. 规格修订

4. `repository-hygiene` 的「用户数据不可误删」清单**移除 `compare/`**（该目录被判定为一次性迭代语料），并新增条目：一次性迭代/验证截图在对应提案归档后 MUST 删除；长期基线以 `docs/ui-baseline/` 为准。

### C. 明确保留（复核结论）

- `ref-suno/`（16 MB，用户提供的 Suno 参考截图，未来 UI 工作仍需对照）；
- `outputs/comparisons/`（空目录）**不是垃圾**——它是应用对比功能的落盘目录，`web/server.py` 的静态挂载在启动时自动创建，删除也会再生，保留；
- `.kimi-code/`（openspec 技能）、`web/static/vendor/`（字体/图标）、`models/`、`web/data/`、`docs/`（含上游 PDF）、`assets/`（上游品牌图）、`oneclick-packages/` 最新构建产物。

### D. 可选（不在本提案范围，用户自便）

曲库里的历史测试歌（如 `Batch A/B`、`Cross Platform Test`、`abc-melody-test-*`、`plan-only-test`、`mlx-test-song`、`legacy-decode-check`、四首 `Untitled` 及验证用歌）属**用户数据库内容**，删除会改变音乐库；如需清除，用户在界面里逐个删除或指定名单由我执行。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `repository-hygiene`: 保留清单移除 `compare/`；新增「一次性迭代语料在归档后删除」规则。

## Impact

- **删除量**：约 11 MB（compare/ 66 个文件）+ 1 个 JSON + 字节码缓存；全部为未入 git 的一次性产物——**删除即不可恢复**（无 git 历史兜底），这是本提案需要用户确认的核心点。
- **归档引用**：`procedural-cover-art` 归档提案对 `compare/cover-options.png` 的引用成为历史记录（不再指向现存文件）。
- **风险**：低。对照/参考类资产（docs/ui-baseline、ref-suno）与全部项目源码、曲库、模型零触碰。
