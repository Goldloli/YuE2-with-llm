# Tasks: style-terms-glossary

## 1. 生成脚本与文档

- [x] 1.1 `tools/export_style_terms.py`：读取 `zh_style_terms.json`；类别表覆盖全部词条（未归类回退「其他」并打印提示）；渲染分组 Markdown（同类别内同义词合并展示）+ 同义词汇总 + 统计头；`--check` 模式；验证：生成后 `--check` 通过
- [x] 1.2 生成并入库 `docs/style-terms.md`；验证：词表先扩至 298 条，文档同步生成 8 组 / 298 条 / 274 个英文标签，无「其他」残留
- [x] 1.3 `tests/test_style_terms_export.py`：文档与再生成逐字一致、无未归类词条；验证：`pytest -q` 全绿

## 2. 一键包集成

- [x] 2.1 `packaging/build_package.py`：`REQUIRED_INSIDE` 加入 `docs/style-terms.md`；构建前执行 `tools/export_style_terms.py --check`（不一致即失败并提示）；验证：临时改文档 → 构建失败；还原 → 成功
- [x] 2.2 `packaging/使用说明.md`：常见问题加入词表指引（指向 `docs/style-terms.md`）
- [x] 2.3 重新构建瘦包并冒烟（`unzip -l` 抽查包内含 `docs/style-terms.md`）

## 3. 校验

- [x] 3.1 `openspec validate style-terms-glossary --strict`；归档；`codegraph sync`
