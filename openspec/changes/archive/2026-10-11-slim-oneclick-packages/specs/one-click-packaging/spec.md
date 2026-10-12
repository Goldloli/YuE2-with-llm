# Spec Delta: one-click-packaging（修订）

## MODIFIED Requirements

### Requirement: 包内容与排除清单

默认构建（无 `--with-models`）MUST 产出不含模型的**通用单包** `yue2-studio-oneclick-<YYYYMMDD>.zip`（双平台启动器、`使用说明.md`、应用源码），MUST NOT 包含 `models/`。显式携带 `--with-models --platform {macos,win-x64}` 时（opt-in 大包模式）：`macos` 包 MUST 内嵌全部模型，`win-x64` 包 MUST 内嵌全部 torch 系模型且 MUST NOT 包含 `models/YuE2-3B-MLX/`，产物 MUST 输出到 `oneclick-packages/<平台>/` 并按平台命名。所有模式 MUST NOT 包含：`.git*`、虚拟环境（`.venv*`）、输出与用户数据（`outputs/`、`web/data/`）、开发治理与参考目录（`openspec/`、`ref-suno/`、`packaging/`）、缓存与构建中间物。

#### Scenario: 安全反扫

WHEN 构建脚本检测到包内存在 `.venv`、`outputs/`、`web/data/`、`.git/` 或 `.env` 任一
THEN 构建 MUST 以非零码失败，不产出 zip

#### Scenario: 包内自检

WHEN 构建完成前检查关键文件
THEN `tools/start.py`、`tools/bootstrap.py`、`web/server.py`、两个启动器与使用说明 MUST 全部在位，`start.command` MUST 通过 bash 语法检查

#### Scenario: 默认瘦包

WHEN 运行 `python packaging/build_package.py`（不带参数）
THEN 产物为不含模型的通用单包（约 10 MiB 级），zip 内 MUST 不存在 `models/` 条目

#### Scenario: 平台模型内嵌

WHEN 构建 `--with-models --platform macos`
THEN 包内含全部模型目录（包括 `YuE2-3B-MLX/` 与 `YuE2-Realaudio/`）；WHEN `--with-models --platform win-x64` THEN 包内不含任何 `YuE2-3B-MLX/` 条目且含全部 torch 系模型
