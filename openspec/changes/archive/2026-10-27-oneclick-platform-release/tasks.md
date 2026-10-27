# Tasks

## 1. 构建器：平台专用包

- [x] 1.1 `packaging/build_package.py` 新增 `--platform {macos,win-x64}`；缺省按构建机判定（darwin→macos、nt→win-x64、其他报错要求显式指定）
- [x] 1.2 只复制对应平台启动器；构建期校验另一平台启动器缺席（出现即非零退出）
- [x] 1.3 产物输出到 `oneclick-packages/<platform>/`，命名 `yue2-studio-oneclick-<YYYYMMDD>-<platform>.zip`
- [x] 1.4 新增 `tests/test_build_package.py`：平台判定、启动器清单、产物命名、缺省平台报错

## 2. 冒烟：平台级校验

- [x] 2.1 `packaging/smoke_package.py` 从文件名识别平台（支持 `--platform` 覆盖），未知平台报错
- [x] 2.2 校验本平台启动器在位、对方启动器缺席、macOS 包 `start.command` 保留可执行位；原红线不变
- [x] 2.3 新增/补充测试：正例通过；人为放入对方启动器、去掉可执行位后失败

## 3. CI：滚动 + 版本 tag 发布

- [x] 3.1 `.github/workflows/oneclick.yml` 矩阵 job 改为 `--platform ${{ matrix.platform }}` 构建 + 冒烟，删除「cp 改名」步骤，仍上传 `oneclick-latest`
- [x] 3.2 新增 `.github/workflows/oneclick-release.yml`：`push tags v*` → prepare 建草稿 release → build-mac / build-windows 并行（构建+冒烟+上传 zip/sha256）→ publish 草稿转正式；重跑复用草稿
- [x] 3.3 `actionlint` 通过；头部注释写清「用户告知版本号后 agent 打 tag」与 macOS 10× 计费提示

## 4. 文档

- [x] 4.1 `packaging/使用说明.md`：包只含当前平台启动器；GitHub Release 两种入口（版本 tag / 滚动 latest）；校验 sha256
- [x] 4.2 `README.md`：两条平台构建命令 + 发布流程（tag `v*` → 自动双包 release）

## 5. 验证（本地 → GitHub）

- [x] 5.1 本机分别构建 `--platform macos` / `--platform win-x64` 并冒烟；确认 mac 包无 `start.bat`、win 包无 `start.command`
- [x] 5.2 `pytest` 全绿；`openspec validate 2026-10-27-oneclick-platform-release --strict` 通过；`actionlint` 通过
- [x] 5.3 commit + push（2afe933/c49a438）→ 滚动 workflow run 40496477988 双平台全绿，`oneclick-latest` 两个资产内容各自独立
- [x] 5.4 打首个版本 tag（`v0.1.7` @ c49a438）→ run 40496505001 全绿：4 个资产、草稿已转正式；下载后 `shasum -c` 两份均 OK，mac 包只有 start.command、win 包只有 start.bat，本地冒烟器复核通过（期间修掉 Windows 侧 CRLF sidecar 问题）
- [x] 5.5 交付本地 macOS 专用包（GitHub release 产物：zip + 解压目录）供用户测试
- [x] 5.6 归档变更（`openspec archive`）
