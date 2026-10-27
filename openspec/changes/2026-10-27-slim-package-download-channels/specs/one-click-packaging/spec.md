## MODIFIED Requirements

### Requirement: 包内容与排除清单

构建 MUST 产出唯一形态的**不含模型的通用单包** `yue2-studio-oneclick-<YYYYMMDD>.zip`（双平台启动器、`使用说明.md`、应用源码），MUST NOT 包含 `models/`；构建脚本 MUST NOT 提供任何内嵌模型的大包模式（`--with-models` / `--platform` 已移除）。所有模式 MUST NOT 包含：`.git*`、虚拟环境（`.venv*`）、输出与用户数据（`outputs/`、`web/data/`）、开发治理与参考目录（`openspec/`、`ref-suno/`、`packaging/`）、缓存与构建中间物。包内 MUST 包含中文风格词表 `docs/style-terms.md`（随 `docs/` 白名单分发），且构建前 MUST 校验该文档与源词表（`src/yue2/data/zh_style_terms.json`）同步——不一致时构建 MUST 以非零码失败并提示重新生成。

#### Scenario: 安全反扫

WHEN 构建脚本检测到包内存在 `.venv`、`outputs/`、`web/data/`、`.git/` 或 `.env` 任一
THEN 构建 MUST 以非零码失败，不产出 zip

#### Scenario: 包内自检

WHEN 构建完成前检查关键文件
THEN `tools/start.py`、`tools/bootstrap.py`、`web/server.py`、`docs/style-terms.md`、两个启动器与使用说明 MUST 全部在位，`start.command` MUST 通过 bash 语法检查

#### Scenario: 词表随包分发

WHEN 构建一键包
THEN zip 内 MUST 存在 `yue2-studio-oneclick/docs/style-terms.md`

#### Scenario: 词表过期阻断构建

WHEN 源词表已更新但 `docs/style-terms.md` 未重新生成
THEN 构建 MUST 以非零码失败并提示运行 `python tools/export_style_terms.py`

#### Scenario: 默认瘦包

WHEN 运行 `python packaging/build_package.py`（不带参数）
THEN 产物为不含模型的通用单包（约 10 MiB 级），zip 内 MUST 不存在 `models/` 条目

#### Scenario: 平台模型内嵌

WHEN 调用方尝试使用旧的内嵌模型参数构建大包
THEN 构建脚本 MUST 以「未知参数」失败（该模式已移除），仓库 MUST NOT 产出任何含 `models/` 的一键包

### Requirement: 产物命名与冒烟

产物 MUST 命名为 `yue2-studio-oneclick-<YYYYMMDD>.zip` 并输出到 `oneclick-packages/`。构建完成后 MUST 对产物做冒烟验证：`unzip -l` 抽查禁用项与包根结构、启动器语法检查；模型权重 MUST NOT 进入归档。归档仍 MUST 使用 zip64 兼容参数。

#### Scenario: 命名与冒烟

WHEN 构建于 2026-10-11 完成
THEN 产物为 `oneclick-packages/yue2-studio-oneclick-20261011.zip`，冒烟校验通过

#### Scenario: 免压缩权重与 zip64

WHEN 检查构建产物条目
THEN 归档内 MUST NOT 存在任何模型权重文件（无需 STORED/zip64 权重处理），zip 仍以 zip64 兼容参数写入以免大目录截断

### Requirement: 首启体验

包内启动器 MUST 在缺环境时引导首启安装：创建虚拟环境、安装依赖（Apple Silicon 另装 MLX 运行时），MUST NOT 在首启链路中下载任何模型权重。首启完成后 MUST 启动本地服务并提示浏览器地址；应用检测到核心模型未安装时 MUST 自动进入「模型」页并提示下载核心模型（约 7.3 GiB），下载源 MUST 可在「国内网络（hf-mirror.com）」与「国外网络（huggingface.co）」之间切换，选择 MUST 持久化并供后续下载复用。使用说明 MUST 覆盖平台要求（Python 3.10+）、首次运行时长预期、模型下载与渠道切换方法、可选组件（扩展模型/转录/MLX）与常见问题（端口、镜像、环境重置）。

#### Scenario: 干净机器首启

WHEN 收件人在装有 Python 3.10+ 的机器上双击启动器
THEN 启动器只完成环境准备并打开 `http://127.0.0.1:7860`，无需任何仓库之外的步骤；页面停在「模型」页提示下载核心模型

#### Scenario: 首启选择国外渠道

WHEN 用户在「模型」页把下载源切到「国际直连」后下载核心模型
THEN 下载经 `https://huggingface.co` 进行，设置持久化为 `download_source=huggingface`

### Requirement: CI 双平台构建与滚动发布

仓库 MUST 提供 GitHub Actions workflow（`.github/workflows/oneclick.yml`）：在 `macos-latest` 与 `windows-latest` 上以矩阵构建**通用源码包**（唯一形态，不含模型），产物按平台命名 `yue2-studio-oneclick-<YYYYMMDD>-{macos,win-x64}.zip` 并附 `.sha256` sidecar。每个产物 MUST 经 `packaging/smoke_package.py` 冒烟：必需条目在位（双启动器、使用说明、`docs/style-terms.md`、`web/server.py` 等），且 MUST NOT 含 `models/`、`web/data/`、`outputs/`、`.git*`、`.venv*`。产物 MUST 发布到滚动 release `oneclick-latest`（同一 tag 下每期**替换**旧资产，不堆积）。触发方式 MUST 为：`push` 到 main（路径过滤至打包相关内容）+ 手动 `workflow_dispatch`。`packaging/build_package.py` MUST 可在 Windows runner 上运行（平台相关校验自适应：跳过 POSIX exec-bit 检查、bash 语法检查使用正斜杠路径）。仓库 MUST NOT 发布任何内嵌模型的一键包（无大包/分卷发布形态）。

#### Scenario: 双平台构建

WHEN push main（打包相关路径）或手动触发 workflow
THEN macos 与 win-x64 两个构建任务各自产出带日期与平台后缀的 zip 与 sha256，冒烟通过

#### Scenario: 滚动发布

WHEN 构建与冒烟全部成功
THEN `oneclick-latest` release 内仅含本期两份 zip 与两份 sha256（旧资产已替换），并标记为最新 release

#### Scenario: 冒烟失败阻断发布

WHEN 任一平台产物冒烟失败（缺必需条目或命中红线）
THEN 该构建任务失败，发布任务不执行、release 不更新

#### Scenario: Windows 构建兼容

WHEN 在 Windows runner 上执行 `python packaging/build_package.py`
THEN 跳过 POSIX exec-bit 检查、bash 语法检查以正斜杠路径执行，构建成功产出 win-x64 资产
