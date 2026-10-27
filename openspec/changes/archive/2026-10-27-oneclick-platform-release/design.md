# Design: 2026-10-27-oneclick-platform-release

## Context

- 现状：`packaging/build_package.py` 是通用单包构建器（两个启动器都打进去），产物 `oneclick-packages/yue2-studio-oneclick-<YYYYMMDD>.zip`；`oneclick.yml` 在 macos/windows 两个 runner 上各构建一次，然后 `cp` 改名上传到滚动 release `oneclick-latest`——两个资产内容一样。
- 参照内部项目的做法：`oneclick-macos.yml` / `oneclick-windows.yml` 两个滚动 workflow（push main → 各自平台包 → 滚动 release），另有 `oneclick-release.yml`（`push tags v*` → prepare 建草稿 → mac/win 并行构建+冒烟+传资产 → publish 草稿转正式）。其发布约定：用户 push 代码后口头告知版本号，agent 执行 `git tag vN && git push origin vN`，其余全自动。
- 用户诉求：yue 也要「GitHub 生成两个一键包 + tag 形式的 release」，收件人拿到的包只含自己平台的内容。

## Goals / Non-Goals

**Goals:**

- 两个平台包各自独立：mac 包只有 `start.command`，win 包只有 `start.bat`。
- 打 `v*` tag 即自动发布版本 release：两个平台并行构建 + 冒烟 + 上传 zip/sha256，草稿全绿后转正式。
- 日常 push main 的滚动 release 继续可用。
- 本地也能一条命令构建任一平台包并冒烟。

**Non-Goals:**

- 不拆两个滚动 workflow（参照项目是因为 mac/win 构建脚本不同才拆；yue 用同一个 Python 构建器 + matrix 更省事，语义等价）。
- 不做安装器（.dmg/.pkg/.exe），仍是解压 + 双击启动器。
- 不改首启流程与模型下载渠道；`--with-models` 保持移除；不触碰 `web/static/`（无视觉变更）。

## Decisions

### D1：`--platform` 参数与默认判定

`build_package.py --platform {macos,win-x64}`；`None` 时按构建机判定（`sys.platform == "darwin"` → macos；`os.name == "nt"` → win-x64；其余报错要求显式指定）。本地在 mac 上零参数即得 mac 包；CI 显式传参。

### D2：输出目录与命名

产物输出到 `oneclick-packages/<platform>/`（该目录已有 `.gitkeep` 且内容被 gitignore 覆盖），命名 `yue2-studio-oneclick-<YYYYMMDD>-<platform>.zip`。与参照项目的 `oneclick-packages/macos/*.zip`、`oneclick-packages/win-x64/*.zip` 结构一致，CI 用通配取包。

### D3：启动器隔离红线

`stage_source(pkg, platform)` 只复制对应启动器；构建期 `self_check` 与冒烟都校验「另一平台启动器缺席」，出现即失败。规格里写成硬要求。

### D4：冒烟按平台校验

`smoke_package.py` 从文件名识别平台（`-macos.zip` / `-win-x64.zip`），支持 `--platform` 覆盖；校验必需条目、本平台启动器、对方启动器缺席、macOS 包 `start.command` 的 zip `external_attr` 保留可执行位；原红线（无 `models/`、`.venv*`、`web/data/`、`outputs/`）不变。sidecar 仍自动生成。

### D5：滚动 workflow

保留 `.github/workflows/oneclick.yml` 单文件 matrix（macos-latest / windows-latest），每腿 `--platform ${{ matrix.platform }}` 构建 + 冒烟，产物直接上传（删除「通用包 cp 改名」步骤）；release 名与资产名不变（`oneclick-latest` + `-macos` / `-win-x64`）。

### D6：版本 tag 正式发布

新增 `.github/workflows/oneclick-release.yml`，照参照项目的三段式：

- 触发 `push: tags: ['v*']`；
- `prepare`（ubuntu，不 checkout）：`gh release view` 存在则复用，否则 `gh release create "$TAG" --draft --repo …`（显式 `--repo`，避免无 `.git` 报错——参照项目 2026-09-28 踩过）；
- `build-mac` / `build-windows`：checkout → setup-python 3.11 → `build_package.py --platform …` → `smoke_package.py` → `gh release upload "$TAG" zip sha256 --clobber`；
- `publish`：`needs: [build-mac, build-windows]`，`gh release edit "$TAG" --draft=false`。
- 任一腿失败 → publish 不执行，草稿保持不可见，可重跑复用。

### D7：tag 规范与发布约定

tag 形如 `v<版本>`（首个建议 `v0.1.7`；与代码版本无关的一键包发布也走同一命名）。操作约定与参照项目一致：用户 push 代码后告知版本号，agent 执行 `git tag vN && git push origin vN`，其余自动。

### D8：release notes

固定中文文案：双平台平台专用一键包（瘦包，不含模型）；首次启动装环境后到「模型」页下载核心模型，可切换国内镜像/国际直连；同名 `.sha256` 供校验；详见包内《使用说明》。

### D9：成本提示

私仓 macOS runner 按 10× 计费：一次滚动 = mac + win 各一跑（约 2–4 分钟/腿）；一次正式发布 = 再加 mac + win 各一跑。workflow 头部注释写明。

## Risks / Trade-offs

- [老脚本按 `oneclick-packages/*.zip` 找产物] → 改为平台子目录 + 文档同步；CI 用通配不受影响。
- [Linux 上无参数构建报错] → 报错信息写明 `--platform macos|win-x64`。
- [首个 tag 版本号拍板] → 建议 `v0.1.7`；若需改版本，删除 release/tag 后重打即可（草稿机制保证半成品不可见）。
- [macOS 计费] → workflow 头部与 proposal 均提示；日常用滚动，正式发布按需打 tag。

## Migration Plan

1. 改造构建器与冒烟（平台参数、目录、命名、红线）。
2. 改滚动 workflow；新增 `oneclick-release.yml`。
3. 文档（使用说明 / README / 发布约定）。
4. 本地构建两个平台包 + 冒烟 + `pytest` + `actionlint`。
5. push → 滚动 CI 冒烟验证；`git tag v0.1.7 && git push origin v0.1.7` → 正式 release 验证两个资产内容各自独立、草稿已转正式。
6. 归档变更。

## Open Questions

- 首个正式版本号用 `v0.1.7`（建议）还是其他？无异议即按建议执行。
