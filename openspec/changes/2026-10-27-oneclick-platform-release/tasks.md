# Tasks

## 1. 构建器：平台专用包

- [ ] 1.1 `packaging/build_package.py` 新增 `--platform {macos,win-x64}`；缺省按构建机判定（darwin→macos、nt→win-x64、其他报错要求显式指定）
- [ ] 1.2 只复制对应平台启动器；构建期校验另一平台启动器缺席（出现即非零退出）
- [ ] 1.3 产物输出到 `oneclick-packages/<platform>/`，命名 `yue2-studio-oneclick-<YYYYMMDD>-<platform>.zip`
- [ ] 1.4 新增 `tests/test_build_package.py`：平台判定、启动器清单、产物命名、缺省平台报错

## 2. 冒烟：平台级校验

- [ ] 2.1 `packaging/smoke_package.py` 从文件名识别平台（支持 `--platform` 覆盖），未知平台报错
- [ ] 2.2 校验本平台启动器在位、对方启动器缺席、macOS 包 `start.command` 保留可执行位；原红线不变
- [ ] 2.3 新增/补充测试：正例通过；人为放入对方启动器、去掉可执行位后失败

## 3. CI：滚动 + 版本 tag 发布

- [ ] 3.1 `.github/workflows/oneclick.yml` 矩阵 job 改为 `--platform ${{ matrix.platform }}` 构建 + 冒烟，删除「cp 改名」步骤，仍上传 `oneclick-latest`
- [ ] 3.2 新增 `.github/workflows/oneclick-release.yml`：`push tags v*` → prepare 建草稿 release → build-mac / build-windows 并行（构建+冒烟+上传 zip/sha256）→ publish 草稿转正式；重跑复用草稿
- [ ] 3.3 `actionlint` 通过；头部注释写清「用户告知版本号后 agent 打 tag」与 macOS 10× 计费提示

## 4. 文档

- [ ] 4.1 `packaging/使用说明.md`：包只含当前平台启动器；GitHub Release 两种入口（版本 tag / 滚动 latest）；校验 sha256
- [ ] 4.2 `README.md`：两条平台构建命令 + 发布流程（tag `v*` → 自动双包 release）

## 5. 验证（本地 → GitHub）

- [ ] 5.1 本机分别构建 `--platform macos` / `--platform win-x64` 并冒烟；确认 mac 包无 `start.bat`、win 包无 `start.command`
- [ ] 5.2 `pytest` 全绿；`openspec validate 2026-10-27-oneclick-platform-release --strict` 通过；`actionlint` 通过
- [ ] 5.3 commit + push → 滚动 workflow 双平台 CI 冒烟绿，`oneclick-latest` 两个资产内容各自独立
- [ ] 5.4 打首个版本 tag（`v0.1.7`）→ 正式 release：mac/win 两个 zip + sha256、草稿已转正式、资产内容各自独立
- [ ] 5.5 交付本地 macOS 专用包（zip + 解压目录）供用户测试
- [ ] 5.6 归档变更（`openspec archive`）
