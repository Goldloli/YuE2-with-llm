# one-click-packaging Specification

## Purpose
TBD - created by archiving change oneclick-packaging. Update Purpose after archive.

## Requirements

### Requirement: 构建区与产物区分离

一键包 MUST 由 `packaging/` 目录内的构建脚本产出，产物 MUST 输出到 `oneclick-packages/` 目录；仓库根目录 MUST NOT 出现一键包产物或启动器散件（启动器源 MUST 存放于 `packaging/launchers/`，用户文档 MUST 存放于 `packaging/使用说明.md`）。`oneclick-packages/` 的产物 MUST 被 `.gitignore` 覆盖（保留 `.gitkeep` 占位）。

#### Scenario: 构建一次一键包

WHEN 运行 `python packaging/build_package.py`
THEN 产物 zip 出现在 `oneclick-packages/` 下，根目录无任何新增文件

### Requirement: 包内容与排除清单

构建 MUST 产出**平台专用、自包含、不含模型**的一键包：包内 MUST 含便携 Python 运行时 `runtime/`（python-build-standalone，对应平台）与全部运行依赖 `envs/web/`（macOS 另含 `envs/mlx/`），MUST 含本平台启动器（`macos` → `start.command`、`win-x64` → `start.bat`）与 `使用说明.md`、共享应用源码；MUST NOT 出现另一平台启动器，MUST NOT 包含 `models/`。构建器 MUST 支持 `--platform {macos,win-x64}` 与 `--runtime {bundle,slim}`（默认 `bundle`；`slim` 仅供开发/快速验证，不用于对外发布）。构建 MUST NOT 依赖收件人机器上的 Python：启动器 MUST 用包内解释器运行应用。所有模式 MUST NOT 包含：`.git*`、虚拟环境（`.venv*`）、输出与用户数据（`outputs/`、`web/data/`）、开发治理与参考目录（`openspec/`、`ref-suno/`、`packaging/`）、缓存与构建中间物。包内 MUST 包含中文风格词表 `docs/style-terms.md`（随 `docs/` 白名单分发），且构建前 MUST 校验该文档与源词表（`src/yue2/data/zh_style_terms.json`）同步——不一致时构建 MUST 以非零码失败并提示重新生成。

#### Scenario: 安全反扫

WHEN 构建脚本检测到包内存在 `.venv`、`outputs/`、`web/data/`、`.git/` 或 `.env` 任一
THEN 构建 MUST 以非零码失败，不产出 zip

#### Scenario: 包内自检

WHEN 构建完成前检查关键文件
THEN `runtime/`（本平台解释器）、`envs/web`、`tools/start.py`、`tools/bootstrap.py`、`web/server.py`、`docs/style-terms.md`、`使用说明.md` 与**本平台启动器** MUST 全部在位；`runtime` MUST 能导入 torch/transformers/fastapi/uvicorn/soundfile，且把 `src` 加入路径后 MUST 能导入 `yue2`；任一包出现对方平台启动器 MUST 以非零码失败

#### Scenario: 词表随包分发

WHEN 构建任一平台的一键包
THEN zip 内 MUST 存在 `yue2-studio-oneclick/docs/style-terms.md`

#### Scenario: 词表过期阻断构建

WHEN 源词表已更新但 `docs/style-terms.md` 未重新生成
THEN 构建 MUST 以非零码失败并提示运行 `python tools/export_style_terms.py`

#### Scenario: 默认瘦包

WHEN 运行 `python packaging/build_package.py`（不带参数）
THEN 产物为构建机所属平台的自包含包（`--runtime bundle` 默认，含 `runtime/` 与 `envs/web`），zip 内 MUST 不存在 `models/` 条目

#### Scenario: 平台模型内嵌

WHEN 调用方尝试使用旧的内嵌模型参数构建大包
THEN 构建脚本 MUST 以「未知参数」失败（该模式已移除），仓库 MUST NOT 产出任何含 `models/` 的一键包

#### Scenario: 平台启动器隔离

WHEN 构建 `--platform macos`
THEN 包内 MUST 只含 `start.command` 且 MUST NOT 含 `start.bat`；WHEN 构建 `--platform win-x64` THEN 包内 MUST 只含 `start.bat` 且 MUST NOT 含 `start.command`

### Requirement: 产物命名与冒烟

平台包 MUST 输出到 `oneclick-packages/<platform>/`，命名 `yue2-studio-oneclick-<YYYYMMDD>-<platform>.zip`，体积 MUST 小于 1.9 GiB（GitHub 单资产 2 GiB 余量）。构建完成后 MUST 冒烟：从文件名识别平台（允许 `--platform` 覆盖），校验必需条目（含 `runtime/` 与 `envs/web`）、另一平台启动器缺席、macOS 包 `start.command` 保留可执行位、无 `models/` 等禁用项；MUST 执行**真冒烟**——解压后以包内解释器导入关键依赖、启动 `web/server.py`、轮询 `/api/state` 成功返回。冒烟 MUST 自动生成 LF 换行的同名 `.sha256` sidecar。模型权重 MUST NOT 进入归档。

#### Scenario: 命名与冒烟

WHEN 构建于 2026-10-11 完成 `--platform macos`
THEN 产物为 `oneclick-packages/macos/yue2-studio-oneclick-20261011-macos.zip`，条目检查与真冒烟（包内 Python 起服务）通过，包内无 `start.bat`

#### Scenario: 免压缩权重与 zip64

WHEN 检查构建产物条目
THEN 归档内 MUST NOT 存在任何模型权重文件（无需 STORED/zip64 权重处理），zip 仍以 zip64 兼容参数写入以免大目录截断

#### Scenario: 跨平台启动器混入被拒

WHEN 冒烟时发现 macOS 包里存在 `start.bat`（或 Windows 包里存在 `start.command`）
THEN 冒烟 MUST 以非零码失败并打印冲突条目

#### Scenario: 真冒烟起服务

WHEN 对自包含包执行冒烟
THEN 解压后的包内 MUST 能在无网络、无外部 Python 的条件下启动 `web/server.py`，且 `/api/state` 返回 JSON 含 `core_installed` 字段

### Requirement: 首启体验

包内启动器 MUST 在启动时**不进行任何依赖安装或联网下载**：检测到包内 `runtime/` 时 MUST 直接以包内解释器启动本地服务并打开浏览器；仅当是开发用瘦包（无 `runtime/`）时才允许走原有的环境引导路径。应用检测到核心模型未安装时 MUST 自动进入「模型」页并提示下载核心模型（约 7.3 GiB），下载源 MUST 可在「国内网络（hf-mirror.com）」与「国外网络（huggingface.co）」之间切换，选择 MUST 持久化并供后续下载复用。使用说明 MUST 覆盖平台要求（macOS Apple Silicon / Windows x64）、包体积与磁盘要求、模型下载与渠道切换、可选组件、Windows GPU 可选升级（CUDA 版 torch）与常见问题（端口、镜像、环境重置）。

#### Scenario: 干净机器首启

WHEN 收件人在装有 macOS（Apple Silicon）或 Windows x64 的机器上解压并双击启动器
THEN 启动器不联网、不安装依赖，用包内运行时直接启动服务并打开 `http://127.0.0.1:7860`，页面停在「模型」页提示下载核心模型

#### Scenario: 首启选择国外渠道

WHEN 用户在「模型」页把下载源切到「国际直连」后下载核心模型
THEN 下载经 `https://huggingface.co` 进行，设置持久化为 `download_source=huggingface`

### Requirement: CI 双平台构建与滚动发布

仓库 MUST 提供滚动发布 workflow（`.github/workflows/oneclick.yml`）：在 `macos-latest` 与 `windows-latest` 上以矩阵**分别构建对应平台的自包含包**（`--platform macos` / `--platform win-x64`，各自只含本平台启动器，不含模型），产物命名 `yue2-studio-oneclick-<YYYYMMDD>-{macos,win-x64}.zip` 并附 `.sha256` sidecar。每个产物 MUST 经平台级冒烟（含真冒烟起服务）。产物 MUST 发布到滚动 release `oneclick-latest`（同一 tag 下每期**替换**旧资产，不堆积）。触发方式 MUST 为：`push` 到 main（路径过滤至打包相关内容）+ 手动 `workflow_dispatch`。构建 MUST 缓存便携 Python 与 pip wheel 以控制耗时与 macOS 10× 计费。仓库 MUST NOT 发布任何内嵌模型的一键包。

#### Scenario: 双平台构建

WHEN push main（打包相关路径）或手动触发 workflow
THEN macos 与 win-x64 两个构建任务各自产出**只含本平台启动器、自带 runtime 与依赖**的 zip 与 sha256，条目检查与真冒烟通过

#### Scenario: 滚动发布

WHEN 构建与冒烟全部成功
THEN `oneclick-latest` release 内仅含本期两份平台 zip 与两份 sha256（旧资产已替换），并标记为最新 release

#### Scenario: 冒烟失败阻断发布

WHEN 任一平台产物冒烟失败（缺入条目、真冒烟起服务失败、混入对方平台启动器或命中红线）
THEN 该构建任务失败，发布任务不执行、release 不更新

#### Scenario: Windows 构建兼容

WHEN 在 Windows runner 上执行 `python packaging/build_package.py --platform win-x64`
THEN 跳过 POSIX exec-bit 检查、bash 语法检查以正斜杠路径执行，构建成功产出 win-x64 自包含资产

### Requirement: 版本 tag 正式发布

仓库 MUST 提供版本发布 workflow（`.github/workflows/oneclick-release.yml`）：以 `push` tag `v*` 触发，并行构建 macOS 与 Windows 两个平台专用**自包含**一键包并挂到该 tag 的 GitHub Release。发布 MUST 采用「先草稿、后转正式」：`prepare` job MUST 先创建（或复用已存在的）**草稿** release；`build-mac` 与 `build-windows` MUST 并行执行「构建 → 平台冒烟（含真冒烟）→ 上传 zip 与 sha256」；仅当两个构建 job 都成功时，`publish` job MUST 将草稿转为正式，任一失败则 MUST 保持草稿且可重跑。Release 资产 MUST 为两个平台 zip（各带同名 `.sha256`），命名与滚动发布一致；Release 说明 MUST 写明「自包含运行时、双击直接打开网页、模型需在应用内下载（可选国内/国际下载源）、核对 sha256、详见包内使用说明」。

#### Scenario: 打 tag 发布双包

WHEN 维护者 push `v0.1.8` tag
THEN workflow 创建草稿 release `v0.1.8`，mac 与 win 两个自包含包并行构建、真冒烟通过后上传，最后草稿自动转正式

#### Scenario: 单平台失败保持草稿

WHEN 任一平台构建或冒烟失败
THEN publish job 不执行，release 保持草稿状态且不出现在公开列表

#### Scenario: 重跑复用草稿

WHEN 同一 tag 的 workflow 重跑
THEN prepare job 复用已存在的 release（不重复创建），`--clobber` 覆盖上传同名资产
