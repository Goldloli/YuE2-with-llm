# Tasks

## 1. 构建器：自包含包

- [ ] 1.1 `build_package.py` 新增 `--runtime {bundle,slim}`（默认 bundle）；bundle 模式下载/缓存 python-build-standalone（PBS 版本钉常量，`YUE2_ONECLICK_CACHE` 可覆盖），解出 `runtime/`
- [ ] 1.2 生成依赖安装列表（pyproject dependencies + `[web]` extras + `torchaudio` 同钉版；mac 追加 `envs/mlx` 的 mlx/mlx-metal/tiktoken/numpy/soundfile），`PYTHONNOUSERSITE=1` 下 `pip install --target envs/web|envs/mlx`
- [ ] 1.3 构建自检：包内 runtime 能 import torch/transformers/fastapi/uvicorn/soundfile；`sys.path` 加 `src` 后能 import yue2；条目红线（无 models/.venv/web/data/outputs、只含本平台启动器）；zip 体积 < 1.9 GiB
- [ ] 1.4 `--runtime slim` 保持现有瘦包行为（本地快速验证用）

## 2. 启动链路：不联网直接起服务

- [ ] 2.1 `packaging/launchers/start.command` / `start.bat`：检测 `runtime/` → 设 `PYTHONPATH="envs/web:src"` 用包内解释器启动 `tools/start.py --bundled`；否则回退现有系统 Python 逻辑
- [ ] 2.2 `tools/start.py` 增加 bundled 模式：跳过 bootstrap/环境检查，直接起 `web/server.py` 并打开浏览器；保留瘦包/开发路径
- [ ] 2.3 `web/server.py` 解释器解析：bundled 时 MLX 走 `runtime + envs/mlx`、转录走 `runtime + envs/web`；开发时回退 `.venv-mlx` / `.venv-sheetsage2`；`mlx_available()`/`transcribe_available()` 同步

## 3. 冒烟与 CI

- [ ] 3.1 `smoke_package.py` 支持自包含包：校验 `runtime/` 与 `envs/web` 关键条目，原有红线不变
- [ ] 3.2 新增 `packaging/smoke_bundle.py`：解压 → 包内 Python import 关键依赖 → 启动服务 → 轮询 `/api/state` → 退出；双平台可跑
- [ ] 3.3 `oneclick.yml` / `oneclick-release.yml` 默认构建 bundle 并跑真冒烟；加 PBS + pip wheel 的 actions/cache；更新头部成本提示

## 4. Windows GPU 与文档

- [ ] 4.1 新增 `tools/install_cuda_torch.py`（NVIDIA 用户可选：把 CUDA 版 torch 装进 `envs/web`）
- [ ] 4.2 `packaging/使用说明.md` 改为「包内自带运行时，双击直接开网页（不联网装依赖）」；写明体积、平台要求、模型仍应用内下载；CUDA 加速为可选步骤
- [ ] 4.3 `README.md` 同步；构建章节写 `--runtime bundle|slim`
- [ ] 4.4 新增 `tests/test_bundle_layout.py`：启动器 bundle 检测、依赖清单生成、冒烟脚本的布局断言（不实际装依赖）

## 5. 验证与交付

- [ ] 5.1 本机构建 mac bundle 并冒烟（真起服务）；核对体积、`runtime/`、`envs/web`、启动器直启路径；确认启动过程不联网（可用 `YUE2_OFFLINE=1` 或断网模拟验证 import 路径）
- [ ] 5.2 `pytest` 全绿；`actionlint`；`openspec validate --strict`
- [ ] 5.3 commit + push → 滚动 CI 双平台绿（自包含包 + 真冒烟），`oneclick-latest` 资产更新
- [ ] 5.4 打 `v0.1.8` → 正式 release 双平台自包含包 + sha256；下载复核（包内 Python 起服务）
- [ ] 5.5 交付本地 macOS 自包含包（zip + 解压目录）供用户测试
- [ ] 5.6 归档变更

## 6. Windows CUDA 加速套件（参考 ASRbox）

- [x] 6.1 `packaging/cuda-requirements-win.txt`（torch==2.10.0，cu128 索引）+ `packaging/build_cuda_kit.py`（--target 安装 → 裁剪 → 逐文件 sha256 manifest → 复现 zip → 分卷 ≤1.9 GiB → `--check`/`--verify-parts` 自检）
- [x] 6.2 `.github/workflows/cuda-kit.yml`：windows runner 构建套件；dispatch 或 `cuda-kit-*` tag 触发；草稿 release →（校验分卷）→ 正式；tag 固定为 `cuda-kit-cu128-torch2.10.0`
- [x] 6.3 `tools/cuda_kit.json`：manifest URL + 预期 torch 版本（随包分发）
- [x] 6.4 `web/cuda_kit.py`：状态机（not_downloaded/downloading/ready/enabled/invalidated）、manifest 校验、分卷 Range 下载（续传/取消/进度）、sha256 校验、安全解压、安装/移除、`nvidia-smi` 探测、`maybe_inject()`（sys.path + add_dll_directory）
- [x] 6.5 `web/server.py`：启动时 `maybe_inject()`；`MODEL_COMPONENTS` 增加 win32 的 `cuda-kit` 条目与运行时状态；下载/取消/删除端点复用或新增
- [x] 6.6 模型页 UI：Windows 专属「CUDA 加速套件」条目（GPU 检测、下载进度/取消、已安装待重启、移除），zh/en 文案；无视觉变更（复用 `.mdl-*` 形态）
- [x] 6.7 `tests/test_cuda_kit.py`：manifest 校验/路径安全/下载-校验-解压（fake fetch）/取消/状态机/平台门控
- [x] 6.8 文档：使用说明（Windows NVIDIA 用户可选安装、约 3 GB、重启生效）、README
- [ ] 6.9 实际发布套件 release（dispatch workflow）并复核资产（manifest + 分卷 sha256、`--verify-parts`）；更新 `tools/cuda_kit.json` 到最终 URL
