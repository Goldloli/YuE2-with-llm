# Spec Delta: repository-hygiene（修订）

## MODIFIED Requirements

### Requirement: 用户数据不可误删

清理 MUST NOT 删除：曲库索引内的歌曲输出、`web/data/`（上传与库数据）、`models/` 权重、用户提供的参考截图目录（`ref-suno/`）、工作流依赖目录（`.kimi-code/`、`.codegraph/`）、应用管理的运行目录（`outputs/comparisons/`，由服务端静态挂载自动创建）。

#### Scenario: 保守边界

WHEN 清理遇到无法明确归类为可再生/一次性的文件
THEN 保留并在提案中列出，交由用户决定

#### Scenario: 应用管理的目录

WHEN 目录由应用运行时自动创建（如 `outputs/comparisons/`）
THEN 视为运行态而非杂物，保留（删除行为亦无效，会被再生）

## ADDED Requirements

### Requirement: 一次性迭代语料在归档后删除

开发过程中的逐轮迭代截图与历史变更验证截图（如 `compare/` 下的 round/extras/model-pill 类文件）MUST 视为一次性产物：在对应变更归档（其描述与结论入档）后 MUST 删除。长期的视觉基线 MUST 以 `docs/ui-baseline/` 为唯一存放处；参考性质的外部截图（如 `ref-suno/`）MUST 收纳于独立参考目录并长期保留。

#### Scenario: 变更归档后的截图清理

WHEN 某变更已归档且其验证截图仅承担一次性的过程证据
THEN 截图删除，长期对照以 `docs/ui-baseline/` 中的基线为准

### Requirement: 构建中间产物

基准/诊断脚本产生的中间文件（如写入 `outputs/` 的临时 JSON）MUST 在测量结束后删除，MUST NOT 混入曲库数据目录长期留存。

#### Scenario: 基准测量收尾

WHEN 一次速度/质量基准测量完成
THEN 其临时输出被清理或移至仓库外（如 `/tmp`），不留在 `outputs/` 内
