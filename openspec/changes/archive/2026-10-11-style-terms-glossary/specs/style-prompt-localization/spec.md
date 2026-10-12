# Spec Delta: style-prompt-localization（新增）

## ADDED Requirements

### Requirement: 词表导出文档

仓库 MUST 提供生成脚本 `tools/export_style_terms.py`，从 `src/yue2/data/zh_style_terms.json` 生成中文风格词表文档 `docs/style-terms.md`。该文档 MUST 为生成物（含「请勿手改」标注与再生成命令）、MUST NOT 手工编辑；内容 MUST 按类别分组渲染为中英对照 Markdown 表格，并附词条统计（总条数与英文去重数）与同义词汇总。词表中每个词条 MUST 归属且仅归属一个类别；新增词条若未在脚本类别表中归类，MUST 归入「其他」并在生成输出中列出提示。脚本 MUST 提供 `--check` 模式：与仓库内文档一致时以 0 退出，不一致时以非零退出并提示重新生成。

#### Scenario: 文档与源数据一致

WHEN 运行 `python tools/export_style_terms.py --check`
THEN 仓库内 `docs/style-terms.md` 与源词表渲染结果逐字一致时校验通过（退出码 0）

#### Scenario: 词表更新后同步

WHEN 向 `zh_style_terms.json` 新增或修改词条后重新运行生成脚本
THEN 文档 MUST 反映全部变更；此前未归类的词条出现在「其他」分组且在生成输出中被列出

#### Scenario: 类别全覆盖

WHEN 测试校验词典与类别表的对应关系
THEN 词典中不存在未归类词条（脚本类别表覆盖全部词条），同义合并展示与同义词汇总 MUST 与词典内容自动对应

#### Scenario: 分组渲染

WHEN 生成文档
THEN 词条按类别分组渲染为表格；同一类别内多个中文词指向同一英文标签时 SHOULD 合并为一行展示；跨类别的同义词组 MUST 出现在同义词汇总中
