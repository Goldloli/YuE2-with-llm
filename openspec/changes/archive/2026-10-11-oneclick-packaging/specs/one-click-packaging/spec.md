# Spec Delta: one-click-packaging（新能力）

## ADDED Requirements

### Requirement: 构建区与产物区分离

一键包 MUST 由 `packaging/` 目录内的构建脚本产出，产物 MUST 输出到 `oneclick-packages/` 目录；仓库根目录 MUST NOT 出现一键包产物或启动器散件（启动器源 MUST 存放于 `packaging/launchers/`，用户文档 MUST 存放于 `packaging/使用说明.md`）。`oneclick-packages/` 的产物 MUST 被 `.gitignore` 覆盖（保留 `.gitkeep` 占位）。

#### Scenario: 构建一次一键包

WHEN 运行 `python packaging/build_package.py`
THEN 产物 zip 出现在 `oneclick-packages/` 下，根目录无任何新增文件

### Requirement: 包内容与排除清单

一键包 MUST 包含：双平台启动器（`start.command` 带可执行位、`start.bat`）、`使用说明.md`、应用源码（`web/ src/ tools/ skills/ examples/ licenses/ docs/` 与许可证/项目元文件）。一键包 MUST NOT 包含：`.git*`、虚拟环境（`.venv*`）、模型权重（`models/`）、输出与用户数据（`outputs/`、`web/data/`）、开发治理与参考目录（`openspec/`、`compare/`、`ref-suno/`、`packaging/`）、缓存与构建中间物。

#### Scenario: 安全反扫

WHEN 构建脚本检测到包内存在 `.venv`、`models/`、`outputs/`、`web/data/`、`.git/` 或 `.env` 任一
THEN 构建 MUST 以非零码失败，不产出 zip

#### Scenario: 包内自检

WHEN 构建完成前检查关键文件
THEN `tools/start.py`、`tools/bootstrap.py`、`web/server.py`、两个启动器与使用说明 MUST 全部在位，`start.command` MUST 通过 bash 语法检查

### Requirement: 产物命名与冒烟

产物 MUST 命名为 `yue2-studio-oneclick-<YYYYMMDD>.zip`。构建完成后 MUST 对产物做冒烟验证：解压到临时目录，确认包根结构（启动器、使用说明、`web/server.py`）与 zip 内容一致。

#### Scenario: 命名与冒烟

WHEN 构建于 2026-10-11 完成
THEN 产物为 `yue2-studio-oneclick-20261011.zip`，冒烟解压校验通过

### Requirement: 首启体验

包内启动器 MUST 在缺环境时引导首启安装（创建虚拟环境、安装依赖、经镜像下载模型），完成后 MUST 启动本地服务并提示浏览器地址；使用说明 MUST 覆盖平台要求（Python 3.10+）、首次运行时长预期、可选组件（扩展模型/转录/MLX）与常见问题（端口、镜像、环境重置）。

#### Scenario: 干净机器首启

WHEN 收件人在装有 Python 3.10+ 的机器上双击启动器
THEN 自动完成环境与模型准备并打开 `http://127.0.0.1:7860`，无需任何仓库之外的步骤
