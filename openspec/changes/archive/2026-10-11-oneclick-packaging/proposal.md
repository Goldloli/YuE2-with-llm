# Proposal: oneclick-packaging

## Why

当前「一键启动」（`start.command` / `start.bat` / `START.md`）直接摊在仓库根目录，用户分发时等于把整个仓库（含 `.venv*`、`models/`、`outputs/`、`web/data/` 用户数据）给出去。用户要求参考 `xiaoheihe_crawler` 项目的做法：**构建区（`packaging/`）+ 产物区（`oneclick-packages/`）分离**——一键包专门构建进一个文件夹，而不是散在/构建到根目录。

参考项目模式（已调研）：`packaging/` 入库存放构建脚本、启动器源、使用说明、素材；`oneclick-packages/<平台>/` 为 gitignore 的产物区；产物命名 `<产品>-oneclick-<平台>-<架构>-<YYYYMMDD>.zip`；包内含自带 runtime + 启动器 + 应用代码 + 使用说明，收件人免安装双击即用。

## What Changes

### 1. 目录重构

```
packaging/                       # 构建区（入库）
├── build_package.py             # 构建脚本（Python，跨平台）
├── launchers/
│   ├── start.command            # 从根目录迁入（macOS/Linux 启动器）
│   └── start.bat                # 从根目录迁入（Windows 启动器）
└── 使用说明.md                   # 由根目录 START.md 迁入并更新
oneclick-packages/               # 产物区（.gitignore 产物，保留 .gitkeep）
└── yue2-studio-oneclick-<YYYYMMDD>.zip
```

- 根目录移除 `start.command` / `start.bat` / `START.md`（源头移入 packaging，避免「构建到根目录」的现状）；
- 仓库开发者自用启动改为 `python tools/start.py`（写进使用说明与 README 提示）。

### 2. 构建脚本 `packaging/build_package.py`

仿参考项目十段式，按 YuE 的实际裁剪：

1. 常量与暂存目录（`mktemp -d` 语义，Python `tempfile`，失败自动清理）；
2. **rsync/tar 风格暂存**：复制源码到暂存包根——包含 `web/ src/ tools/ skills/ examples/ licenses/ docs/ pyproject.toml README.md LICENSE MODEL_LICENSE THIRD_PARTY_NOTICES.md MANIFEST.in tests/ .github/`；**排除**：`.git* .venv* .codegraph .kimi-code .playwright-mcp .pytest_cache __pycache__ *.egg-info models/ outputs/ web/data/ compare/ ref-suno/ openspec/ packaging/ oneclick-packages/ dist/` 及全部 `*.png` 根级散图；
3. 复制启动器（`packaging/launchers/*`，`start.command` 置可执行位）与 `packaging/使用说明.md`；
4. **安全反扫**：断言包内不存在 `venv/ models/ outputs/ web/data/ .git/ .env` 等任一命中即失败退出；
5. **包内自检**：断言关键文件在位（`tools/start.py`、`tools/bootstrap.py`、`web/server.py`、两个启动器、使用说明）；启动器脚本语法检查（`bash -n`）；
6. 打包 `zip`（排除 `__MACOSX`），输出 `oneclick-packages/yue2-studio-oneclick-<YYYYMMDD>.zip`；
7. 打印产物路径与大小摘要。

### 3. 首次运行体验（沿用现有 bootstrap）

包内双击启动器 → `tools/start.py` → 检测缺 `.venv`/`models/` 时走 `tools/bootstrap.py`（建 venv、按平台装依赖、经 hf-mirror 下载模型）→ 启动 `http://127.0.0.1:7860`。要求收件人自备 Python 3.10+（与现状一致）。

### 4. 非目标（Non-goals，含与参考项目的关键差异声明）

- **不内置便携 Python runtime 与三套依赖/模型**：YuE 的 torch 三环境 + 模型合计约 15 GB，与参考项目（轻依赖，620 MB 级）不同量级；本包定为「源码 + 启动器 + 首启自动安装」形态。若将来需要「免安装全内置」包，属另一个体积量级的工程，另案评估；
- 不做平台专属包目录（`macos/` / `win-x64/`）：bootstrap 包为**通用包**（内含双平台启动器），单文件输出即可；将来真做平台专属全内置包时再引入平台子目录；
- 不动 `tools/build_release.py`（pip wheel + skill 包，产物 `dist/` 维持现状）；
- 不做代码签名/公证（macOS Gatekeeper 说明写在使用说明里）。

## Capabilities

### New Capabilities

- `one-click-packaging`: 一键包的构建契约——目录布局（packaging/ + oneclick-packages/）、包内容与排除清单、命名规范、安全反扫与包内自检、首启 bootstrap 体验。

### Modified Capabilities

（无）

## Impact

- **代码**：新增 `packaging/build_package.py`；`packaging/launchers/{start.command,start.bat}`、`packaging/使用说明.md`（源文件迁移）；根目录删除三个启动相关文件；`.gitignore` 增加 `oneclick-packages/*` 产物规则（保留 `.gitkeep`）；README 增补「构建一键包」一节与自用启动说明。
- **风险**：低。包内不含用户数据/模型/密钥由反扫保证；根目录启动器移除后仓库自用路径（`python tools/start.py`）在使用说明与 README 双处注明。
