# Spec Delta: repository-hygiene（新能力）

## ADDED Requirements

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

清理 MUST NOT 删除：曲库索引内的歌曲输出、`web/data/`（上传与库数据）、`models/` 权重、参考截图目录（`ref-suno/`、`compare/`）、工作流依赖目录（`.kimi-code/`、`.codegraph/`）。

#### Scenario: 保守边界

WHEN 清理遇到无法明确归类为可再生/一次性的文件
THEN 保留并在提案中列出，交由用户决定
