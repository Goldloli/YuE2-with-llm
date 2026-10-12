# Tasks: oneclick-packaging

## 1. 目录与源文件迁移

- [x] 1.1 新建 `packaging/launchers/`，迁入 `start.command`（保留可执行位）与 `start.bat`；根目录删除两份原文件；验证：`packaging/launchers/` 下脚本可执行、根目录无启动器
- [x] 1.2 `START.md` 升级为 `packaging/使用说明.md`：增补「构建者小节」（构建命令、产物位置）与「自用启动 = `python tools/start.py`」；根目录删除 START.md
- [x] 1.3 新建 `oneclick-packages/` + `.gitkeep`；`.gitignore` 增加 `oneclick-packages/*` 与 `!oneclick-packages/.gitkeep`；验证：git status 干净

## 2. 构建脚本

- [x] 2.1 `packaging/build_package.py`：白名单复制（INCLUDE_ROOTS/EXCLUDE_PATTERNS 见 design 决策 4）+ 启动器与使用说明入包 + 安全反扫（FORBIDDEN 命中即失败）+ 包内自检（关键文件、`bash -n`）+ zip 输出 `oneclick-packages/yue2-studio-oneclick-<YYYYMMDD>.zip` + `--keep-stage` 排查开关；验证：脚本 `--help` 正常
- [x] 2.2 构建实测：跑一次完整构建；验证：zip 产出、大小合理（百 MB 内）、`unzip -l` 无禁用项
- [x] 2.3 冒烟：解压产物到临时目录，核对包根（启动器×2、使用说明.md、`web/server.py`、`tools/start.py`）；对解压出的 `start.command` 做 `bash -n`；验证：全部在位
- [x] 2.4 反扫负例：临时向暂存目录塞一个 `models/` 假目录，确认构建失败退出（随后移除假目录）；验证：退出码非零

## 3. README 与联动

- [x] 3.1 README 增补「一键包」小节（构建命令、产物命名、首启说明、自用启动）；验证：无失效链接
- [x] 3.2 与 repo-cleanup 变更联动核对（START.md/根目录启动器的删除只执行一次）；验证：`openspec validate oneclick-packaging --strict` 通过；归档；`codegraph sync`
