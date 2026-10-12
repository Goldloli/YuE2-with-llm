# Tasks: bundled-model-packages

## 1. 构建脚本平台化

- [x] 1.1 `packaging/build_package.py`：新增 `--platform {macos,win-x64}`；平台模型清单（macos=全部、win-x64=除 YuE2-3B-MLX）；输出 `oneclick-packages/<platform>/` + 平台命名
- [x] 1.2 zip 直写：models/ 不进暂存，zip 阶段按需以 `STORED` 从源目录直接写入（zip64）；其余文件 `DEFLATED`
- [x] 1.3 反扫调整（平台包允许 models/）+ 平台断言自检（macos 含 MLX 目录、win-x64 不含）+ `.gitignore` 平台 `.gitkeep` 例外
- [x] 1.4 冒烟：`unzip -l` 抽查两包（模型条目在、无 .venv/outputs/web-data）+ 解压启动器语法检查（用 `--out-dir /tmp` 小流量验证脚本逻辑后再执行全量构建）

## 2. 构建与实测

- [x] 2.1 macOS 全模型包构建；验证：约 23 GB、`unzip -l | grep YuE2-3B-MLX` 条目在、自检通过
- [x] 2.2 win-x64 包构建；验证：约 12.4 GB、无 MLX 条目
- [x] 2.3 删除旧通用包 `oneclick-packages/yue2-studio-oneclick-20261011.zip`
- [x] 2.4 真机启动冒烟（macOS 包）：解压到 /tmp，用包内 start.command（`--skip-models` 等价路径）确认 bootstrap 识别到自带模型并跳过下载；结束后清理

## 3. 文档与校验

- [x] 3.1 `packaging/使用说明.md`：首启流程（模型已随包）、磁盘要求、Windows 解压提示、平台差异
- [x] 3.2 `openspec validate bundled-model-packages --strict`；归档；`codegraph sync`
