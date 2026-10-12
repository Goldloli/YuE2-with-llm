# Spec Delta: one-click-packaging（修订）

## MODIFIED Requirements

### Requirement: 包内容与排除清单

一键包 MUST 按平台构建并输出到 `oneclick-packages/<平台>/`：`macos` 包 MUST 内嵌全部模型（torch 系 + MLX 变体 + 转录与 realaudio 扩展），`win-x64` 包 MUST 内嵌全部 torch 系模型且 MUST NOT 包含 `models/YuE2-3B-MLX/`。两包 MUST 包含：双平台启动器（`start.command` 带可执行位、`start.bat`）、`使用说明.md`、应用源码（`web/ src/ tools/ skills/ examples/ licenses/ docs/` 与许可证/项目元文件）。一键包 MUST NOT 包含：`.git*`、虚拟环境（`.venv*`）、输出与用户数据（`outputs/`、`web/data/`）、开发治理与参考目录（`openspec/`、`ref-suno/`、`packaging/`）、缓存与构建中间物。

#### Scenario: 安全反扫

WHEN 构建脚本检测到包内存在 `.venv`、`outputs/`、`web/data/`、`.git/` 或 `.env` 任一
THEN 构建 MUST 以非零码失败，不产出 zip

#### Scenario: 包内自检

WHEN 构建完成前检查关键文件
THEN `tools/start.py`、`tools/bootstrap.py`、`web/server.py`、两个启动器与使用说明 MUST 全部在位，`start.command` MUST 通过 bash 语法检查

#### Scenario: 平台模型内嵌

WHEN 构建 `--platform macos`
THEN 包内含全部模型目录（包括 `YuE2-3B-MLX/` 与 `YuE2-Realaudio/`）；WHEN 构建 `--platform win-x64` THEN 包内不含任何 `YuE2-3B-MLX/` 条目且含全部 torch 系模型

### Requirement: 产物命名与冒烟

产物 MUST 命名为 `yue2-studio-oneclick-macos-applesilicon-<YYYYMMDD>.zip` 与 `yue2-studio-oneclick-win-x64-<YYYYMMDD>.zip`，分别位于 `oneclick-packages/macos/` 与 `oneclick-packages/win-x64/`。模型权重文件 MUST 以 `STORED`（免压缩）方式写入归档，其余文件 SHOULD 使用 `DEFLATED`。构建完成后 MUST 对产物做冒烟验证：`unzip -l` 抽查模型条目与禁用项、包根结构与启动器语法检查。

#### Scenario: 命名与冒烟

WHEN 构建于 2026-10-11 完成 macOS 平台包
THEN 产物为 `yue2-studio-oneclick-macos-applesilicon-20261011.zip`，冒烟解压校验通过

#### Scenario: 免压缩权重与 zip64

WHEN 归档包含 6.8 GB 单文件权重
THEN 归档以 zip64 写入且该条目为 STORED，构建完成并在冒烟中可列出
