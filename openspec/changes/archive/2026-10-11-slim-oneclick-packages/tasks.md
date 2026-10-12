# Tasks: slim-oneclick-packages

## 1. 构建脚本与产物

- [x] 1.1 `packaging/build_package.py`：默认分支=不含模型（通用单包 → `oneclick-packages/` 根）；`--with-models` 显式开启现状大包路径（平台子目录/命名不变）；验证：三种调用（默认/--with-models macos/--skip-models 调试）输出正确
- [x] 1.2 删除 `oneclick-packages/macos/` 与 `oneclick-packages/win-x64/` 内的两个大包（保留 .gitkeep 骨架）；验证：目录仅剩 .gitkeep
- [x] 1.3 构建新源码包并冒烟（zip 抽查无 models、启动器语法、反扫）；验证：产物 ≈10 MiB

## 2. 文档

- [x] 2.1 `packaging/使用说明.md`：模型不随包 → 首启 bootstrap 下载核心；其余组件走应用内「模型」页（含下载源切换说明）；`--with-models` 大包模式备注
- [x] 2.2 README「One-click package」小节同步

## 3. 校验

- [x] 3.1 `openspec validate slim-oneclick-packages --strict`；归档；`codegraph sync`
