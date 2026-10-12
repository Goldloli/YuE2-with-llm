# repository-hygiene Specification

## Purpose
TBD - created by archiving change repo-cleanup. Update Purpose after archive.

## Requirements

### Requirement: 根目录整洁

仓库根目录 MUST 只存放项目本体（源码、文档、构建与脚本目录、配置、许可文件）；缓存、会话追踪、一次性测试产物 MUST NOT 出现在根目录。参考截图 MUST 收纳于 `ref-suno/` 等参考目录，示例数据 MUST 收纳于 `examples/`，启动器与用户文档 MUST 收纳于 `packaging/`（见 one-click-packaging）。

#### Scenario: 新增会话副产品

WHEN 开发过程产生新的截图/日志/临时产物目录（如工具缓存）
THEN 该目录 MUST 被加入 `.gitignore` 并在提交前清理，不留在根目录

### Requirement: 可再生文件处置

缓存与构建中间物（`__pycache__/`、`.pytest_cache/`、`.playwright-mcp/`、`*.egg-info/`、`.DS_Store`、空缓存目录）MUST 视为可再生：可随时删除，且 MUST 被 `.gitignore` 覆盖。输出目录（`outputs/`）中不在曲库索引（`web/data/library.json`）内的孤儿目录 MUST 定期清理。

#### Scenario: 清理孤儿输出

WHEN `outputs/` 中出现不在曲库索引内的目录
THEN 人工核实为一次性产物后删除，曲库内歌曲及其产物不受影响

### Requirement: 用户数据不可误删

清理 MUST NOT 删除：曲库索引内的歌曲输出、`web/data/`（上传与库数据）、`models/` 权重、用户提供的参考截图目录（`ref-suno/`）、工作流依赖目录（`.kimi-code/`、`.codegraph/`）、应用管理的运行目录（`outputs/comparisons/`，由服务端静态挂载自动创建）。

#### Scenario: 保守边界

WHEN 清理遇到无法明确归类为可再生/一次性的文件
THEN 保留并在提案中列出，交由用户决定

#### Scenario: 应用管理的目录

WHEN 目录由应用运行时自动创建（如 `outputs/comparisons/`）
THEN 视为运行态而非杂物，保留（删除行为亦无效，会被再生）

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
