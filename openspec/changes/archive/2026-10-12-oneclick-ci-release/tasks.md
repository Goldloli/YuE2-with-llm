# Tasks: oneclick-ci-release

## 1. 构建侧

- [x] 1.1 `packaging/build_package.py` Windows 兼容（CI 实跑迭代出三处）：
  - `PYTHONUTF8=1`（workflow 级）+ 脚本 `stdout.reconfigure(errors="replace")`——runner 控制台 cp1252，打印中文文件名（使用说明.md）触发 UnicodeEncodeError
  - POSIX 专属校验（exec-bit、`bash -n`）仅在非 win32 执行——Windows 检出的 `start.command` 为 CRLF，`bash -n` 报语法错误（已本地复现）；macos 构建覆盖同一份源码树
  - `.gitattributes` 为 `*.command` 固定 `eol=lf`
- [x] 1.2 新增 `packaging/smoke_package.py`：必需条目 + 红线（models/web-data/outputs/.git/.venv）+ sha256 sidecar；本地与 CI 均通过

## 2. CI

- [x] 2.1 新增 `.github/workflows/oneclick.yml`：macos-latest + windows-latest 矩阵构建 → 按平台重命名 + 冒烟 → artifacts（retention 3 天）→ release job 更新滚动 `oneclick-latest`（清旧资产 + 上传 + --latest）
- [x] 2.2 `tests.yml` 修复：安装 `.[test,web]`
- [x] 2.3 `.gitignore` 增补 `dist/`
- [x] 2.4 推送后 CI 实跑：`One-click packages` 双平台构建成功（run 38223740753）；`CPU tests` 转绿（run 38224004930）

## 3. 发布验证

- [x] 3.1 校验 `oneclick-latest` release：两份 zip（~9.4MB）+ 两份 sha256 在位；**下载回来对拍 sha256 均 MATCH**
- [x] 3.2 CI 实跑另修：`test_download_installed_component_conflicts` 改为自造已安装组件（monkeypatch ROOT + 假组件），消除对本地模型文件的依赖（原实现在无模型环境 StopIteration）

## 4. 收尾

- [x] 4.1 `openspec validate oneclick-ci-release --strict`；归档；`codegraph sync`
