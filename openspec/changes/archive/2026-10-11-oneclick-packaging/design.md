# Design: oneclick-packaging

## 与参考项目的对照

| 维度 | 参考项目 | 本项目 | 差异原因 |
|---|---|---|---|
| 目录布局 | `packaging/` + `oneclick-packages/<平台>/` | `packaging/` + `oneclick-packages/`（通用包单目录） | bootstrap 包一包通吃双平台，无需平台子目录 |
| 运行时 | 自带便携 Python + pip --target 分层依赖 + 浏览器 | 首启 bootstrap 现建 venv + 拉依赖 | torch 三环境 + 模型 ≈ 15GB，全内置不可分发性 |
| 启动器 | 包内 `start.command`/`start.bat` 注入 env 变量 | 包内同名启动器，薄封装 `tools/start.py` | 逻辑已在 tools/，启动器保持薄 |
| 安全反扫 | 敏感文件零容忍 | 同款思路：禁 `.venv/models/outputs/web-data/.git/.env` | 一致 |
| 命名 | `<产品>-oneclick-<平台>-<架构>-<日期>.zip` | `yue2-studio-oneclick-<日期>.zip` | 通用包无平台/架构段 |

## 关键决策

### 决策 1：bootstrap 包而非全内置包

YuE 的可分发性瓶颈是体积：torch（macOS arm64 wheel 数百 MB，Linux CUDA 版 2GB+）×三套环境 + 模型 7.5GB + MLX 7GB。全内置包 ≈ 15–20GB，zip 传输/校验/更新都不可行。bootstrap 包体积约百 MB 级（纯源码），首启自动下载（hf-mirror 已验证），与仓库现有的 `tools/bootstrap.py` 设计完全一致——即本次是「把已有一键体验组织进构建体系」，不是发明新机制。全内置方案保留为未来可选项（见 Non-goals）。

### 决策 2：根目录启动器移除，自用路径写进文档

`start.command`/`start.bat`/`START.md` 的「源」移入 `packaging/`；根目录不再保留任何启动器（彻底贯彻「不散在根目录」）。仓库开发者自用启动 = `python tools/start.py`（等价入口，bootstrap 逻辑不变）；构建脚本把启动器复制进每个包。`使用说明.md` 与 README 双处注明这一点，防止自用者迷路。

### 决策 3：构建脚本用 Python 而非双平台脚本对

参考项目因运行时体系复杂用了 shell+ps1 双脚本；本项目构建动作（复制+驱逐+zip+自检）全部是跨平台纯标准库操作，单一 `packaging/build_package.py`（仅用 `zipfile/tempfile/shutil/pathlib/subprocess`）即可，且天然可被 CI/未来的脚本调用。`--keep-stage` 参数保留暂存目录便于排查（对齐参考项目的 `KEEP_STAGE=1`）。

### 决策 4：排除清单为白名单式维护

构建脚本维护两份显式清单：`INCLUDE_ROOTS`（顶层条目）与 `EXCLUDE_PATTERNS`（时间性产物，如 `__pycache__`、`*.pyc`、`.DS_Store`、`*.egg-info`）。反扫则在打包前反向断言 `FORBIDDEN`（`.venv* models outputs web/data .git .env .playwright-mcp`）——新增目录默认**不进包**（白名单），漏加会体现在包内自检的缺失报错，而不是悄悄泄漏（黑名单式的风险相反）。

### 决策 5：使用说明是文案真源

`packaging/使用说明.md` 为唯一文案真源（由 `START.md` 升级：增补构建者小节与自用启动命令），每次构建复制进包根，与参考项目的 `packaging/使用说明.md` 模式一致。

## 风险与缓解

- **盲区文件**：未来新增的顶层目录会被白名单挡在包外——包内自检（关键文件清单）会在构建时报错提醒同步脚本；
- **zip 中文名**：本包内不含中文文件名（使用说明.md 为中文名！）——macOS `zip` 对 UTF-8 名默认 OK；脚本显式设置 UTF-8 flag（`zipfile` 默认写 UTF-8 标记），Windows 端解压兼容；
- **首启失败态**：bootstrap 已有的幂等重入（venv 半成品可重建、下载断点续传）不变；使用说明补充「环境重置」步骤。
