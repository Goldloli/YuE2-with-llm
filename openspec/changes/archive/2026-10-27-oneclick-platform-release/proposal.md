# Proposal: 2026-10-27-oneclick-platform-release

## Why

当前一键包是「通用单包」：一份 zip 同时含 macOS 的 `start.command` 与 Windows 的 `start.bat`；CI 只是把它按平台改名上传到滚动 release `oneclick-latest`，没有版本化的正式 Release。用户要求对齐另一个内部项目的做法：

- GitHub 生成**两个独立的一键包**：macOS 专属、Windows 专属，互不含对方平台的启动器；
- 以 **tag + GitHub Release** 形式发布：打 `v*` tag → Actions 并行构建两个包并冒烟 → 挂到该版本 release（先建草稿，两个平台都全绿后自动转正式）；
- 日常 push main 仍保留滚动 release，供随手取最新包。

## What Changes

- **平台专用包（构建器 + 冒烟）**
  - `packaging/build_package.py` 新增 `--platform {macos,win-x64}`：只复制本平台启动器；不带参数时按构建机自动判定（darwin→macos、Windows→win-x64、其他平台要求显式指定）；
  - 产物输出到 `oneclick-packages/<platform>/`，命名 `yue2-studio-oneclick-<YYYYMMDD>-<platform>.zip`；
  - 红线：macOS 包 MUST NOT 含 `start.bat`，Windows 包 MUST NOT 含 `start.command`；
  - `packaging/smoke_package.py` 从文件名识别平台（支持 `--platform` 覆盖），校验本平台启动器在位、对方启动器缺席、macOS 包 `start.command` 保留可执行位。
- **新增版本 tag 发布 workflow**（对齐参照项目）：`.github/workflows/oneclick-release.yml`
  - 触发：`push` tag `v*`；
  - `prepare` 建**草稿** release → `build-mac` / `build-windows` 并行（checkout → setup-python → `build_package.py --platform` → 冒烟 → `gh release upload` zip + sha256）→ `publish` 草稿转正式；
  - 重跑场景复用已存在的草稿 release（`--clobber` 覆盖资产）。
- **滚动 workflow 改造**：现有 `.github/workflows/oneclick.yml` 的矩阵 job 改为 `--platform ${{ matrix.platform }}` 构建平台专用包，仍上传到 `oneclick-latest` 滚动 release（资产名不变：`-macos` / `-win-x64`）。
- **文档**：`packaging/使用说明.md` 写明包只含当前平台启动器、GitHub Release 两种入口（版本 tag / 滚动 latest）；`README.md` 更新构建命令与发布流程；沿用参照项目的发布约定——**用户 push 代码后告知版本号，由 agent 执行 `git tag vN && git push origin vN`，其余全自动**。
- **规格**：MODIFIED `one-click-packaging`（平台专用包、命名与目录、冒烟、滚动发布）；ADDED「版本 tag 正式发布」要求。

## Capabilities

### Modified Capabilities

- `one-click-packaging`：交付形态从「通用单包（双启动器）」改为「双平台各自独立、互不含对方启动器」；产物目录/命名与冒烟按平台；滚动发布保留；新增 tag 触发的正式版本发布（草稿→并行构建→转正式）。

## Impact

- 修改：`packaging/build_package.py`、`packaging/smoke_package.py`、`.github/workflows/oneclick.yml`、`packaging/使用说明.md`、`README.md`。
- 新增：`.github/workflows/oneclick-release.yml`、`tests/test_build_package.py`（平台判定、启动器过滤、命名、冒烟红线）。
- 外部动作：push 后滚动 workflow 重建 `oneclick-latest`；随后打首个版本 tag（建议 `v0.1.7`）触发正式 release，核验两个平台资产内容各自独立。私仓 macOS runner 按 10× 计费，单次发布 = mac + win 各一跑。
- 兼容性：`--with-models` 保持移除；`build_package.py` 无参数仍可用（默认本机平台）；CI 资产名不变；不触碰 `web/static/`（无视觉变更）。
