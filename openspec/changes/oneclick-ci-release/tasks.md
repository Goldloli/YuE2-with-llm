# Tasks: oneclick-ci-release

## 1. 构建侧

- [x] 1.1 `packaging/build_package.py` Windows 兼容：`sys.platform != "win32"` 时校验 exec-bit；bash 语法检查路径 `replace("\\", "/")`
- [x] 1.2 新增 `packaging/smoke_package.py`：必需条目 + 红线（models/web-data/outputs/.git/.venv）+ sha256 sidecar；本地对真实产物验证通过

## 2. CI

- [x] 2.1 新增 `.github/workflows/oneclick.yml`：macos-latest + windows-latest 矩阵构建 → 按平台重命名 + 冒烟 → artifacts（retention 3 天）→ release job 更新滚动 `oneclick-latest`（清旧资产 + 上传 + --latest）
- [x] 2.2 `tests.yml` 修复：安装 `.[test,web]`
- [x] 2.3 `.gitignore` 增补 `dist/`
- [ ] 2.4 推送后观察 CI：`oneclick` workflow 双平台构建成功、`CPU tests` 转绿（本地无 runner，须在 GitHub 验证）

## 3. 发布验证

- [ ] 3.1 校验 `oneclick-latest` release：两份 zip + 两份 sha256 在位；下载 sha256 与本地 sidecar 对拍（抽样一个平台）

## 4. 收尾

- [ ] 4.1 `openspec validate oneclick-ci-release --strict`；归档；`codegraph sync`
