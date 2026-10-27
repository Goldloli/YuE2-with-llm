## MODIFIED Requirements

### Requirement: CI 双平台构建与滚动发布

仓库 MUST 提供 GitHub Actions workflow（`.github/workflows/oneclick.yml`）：在 `macos-latest` 与 `windows-latest` 上以矩阵构建**通用源码包**（默认瘦包），产物按平台命名 `yue2-studio-oneclick-<YYYYMMDD>-{macos,win-x64}.zip` 并附 `.sha256` sidecar。每个产物 MUST 经 `packaging/smoke_package.py` 冒烟：必需条目在位（双启动器、使用说明、`docs/style-terms.md`、`web/server.py` 等），且 MUST NOT 含 `models/`、`web/data/`、`outputs/`、`.git*`、`.venv*`。产物 MUST 发布到滚动 release `oneclick-latest`（同一 tag 下每期**替换**旧资产，不堆积）。触发方式 MUST 为：`push` 到 main（路径过滤至打包相关内容）+ 手动 `workflow_dispatch`。`packaging/build_package.py` MUST 可在 Windows runner 上运行（平台相关校验自适应：跳过 POSIX exec-bit 检查、bash 语法检查使用正斜杠路径）。含模型的大包 MUST 经分卷（单分卷 ≤1.9 GiB）切分后走 GitHub Release，分档、构建与发布流程见 `model-bundle-release` 能力规格。

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
