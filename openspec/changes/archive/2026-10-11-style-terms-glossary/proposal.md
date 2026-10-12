# Proposal: style-terms-glossary

## Why

内置中文风格词表（`src/yue2/data/zh_style_terms.json`，218 条）目前只以 JSON 形式存在于代码内部，用户无从得知「哪些中文词会被识别、会被译成什么英文标签」。用户要求将词表导出一份放进项目，并随一键包一并分发，便于查阅与对照。

## What Changes

（文档与构建变更，无视觉变化、无运行时行为变化）

1. **新增生成脚本** `tools/export_style_terms.py`：从 `zh_style_terms.json` 生成 `docs/style-terms.md`——按类别分组的中英对照 Markdown 表格（表内同义合并）+ 同义词汇总 + 统计信息；提供 `--check` 校验模式（一致退 0，不一致退非零）；
2. **新增生成物** `docs/style-terms.md` 并入库（由脚本生成，禁止手改）；
3. **新增测试** `tests/test_style_terms_export.py`：校验文档与源词表同步、词条类别全覆盖（无未归类残留）；
4. **一键包集成**：`packaging/build_package.py` 自检清单加入 `docs/style-terms.md`，构建前执行 `--check` 校验词表同步（过期即失败并提示重新生成）；`packaging/使用说明.md` 常见问题增加词表指引；
5. **规格更新**：`style-prompt-localization` 新增「词表导出文档」要求；`one-click-packaging` 修订「包内容与排除清单」。

非目标（Non-goals）：不改运行时翻译逻辑与词表内容本身（词条增删另行提案）；不做 CSV / 网页版词表；不改任何界面。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `style-prompt-localization`: 新增词表导出文档要求——生成脚本、与源词表逐条同步、词条类别全覆盖、`--check` 校验模式。
- `one-click-packaging`: 包内容契约修订——包内 MUST 含 `docs/style-terms.md`（随 `docs/` 白名单分发），构建前 MUST 校验词表导出与源词表同步。

## Impact

- **代码**：`tools/export_style_terms.py`（新增）、`tests/test_style_terms_export.py`（新增）、`packaging/build_package.py`（自检清单 + 构建前校验）、`packaging/使用说明.md`（指引一行）。
- **文档**：新增 `docs/style-terms.md`（生成物，随一键包分发）。
- **产物**：一键包体积增加约 10 KiB，可忽略。
- **风险**：低——纯新增文档与校验；生成脚本只读词表 JSON，不触碰运行时路径。
