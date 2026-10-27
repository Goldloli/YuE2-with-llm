# Proposal: 2026-10-27-self-contained-oneclick-bundle

## Why

当前一键包是「瘦包 + 首次启动 pip 装依赖」：双击启动器后要联网 `pip install -e .[web]`（torch 等约 1–2 GiB，mac 上实测要跑好几分钟），用户看到的是长时间滚动的下载日志；**模型不会在启动时下载**（要进「模型」页手动点），但依赖这一步已经足够劝退。

用户要求对齐另一个项目（另一个内部项目（舆情监控））的形态：**便携 Python runtime 与全部依赖都打进包里**，双击启动器**不联网、直接打开网页**；模型仍然不随包分发，进应用后在「模型」页按需下载（可选国内镜像 / 国际直连）。

## What Changes

- **包内自带运行时**：新增自包含模式（默认），包内新增
  - `runtime/`：便携 Python（python-build-standalone，cpython 3.11.x，stripped 版）；
  - `envs/web/`：应用全部依赖（`pip install --target`，含 torch、transformers、fastapi/uvicorn、torchaudio 等，供应用与音频转录共用）；
  - `envs/mlx/`（仅 macOS）：MLX 运行时（`mlx` + `mlx-metal`），让 MLX 引擎免安装可用。
- **启动器直接起服务**：`start.command` / `start.bat` 检测到 `runtime/` 时，用包内 Python + `envs/web` 直接启动 `web/server.py` 并打开浏览器；**不执行 bootstrap、不 pip、不联网**。没有 `runtime/` 的瘦包（开发用）保留原 bootstrap 回退路径。
- **服务端解释器解析适配**：`web/server.py` 对 MLX、SheetSage2 转录的 Python 解释器解析兼容「包内 envs」与「开发用 venv」两种布局；`tools/start.py` 增加 bundle 模式（跳过环境准备，直接起服务）。
- **构建**：`packaging/build_package.py` 新增 `--runtime {bundle,slim}`（默认 `bundle`，`slim` 保持现在的瘦包用于快速开发验证）；bundle 模式下载/复用便携 Python、`pip install --target` 装依赖、构建时自检（`import torch/fastapi/...` + `import yue2`），产物仍输出到 `oneclick-packages/<platform>/`；体积预估 mac ≈ 250–350 MB、win ≈ 250–300 MB（远低于 GitHub 单资产 2 GiB 上限）。
- **冒烟升级**：`packaging/smoke_package.py` 校验自包含条目（`runtime/`、`envs/web`）；新增 `packaging/smoke_bundle.py` 做「解压 → 用包内 Python import 关键依赖 → 起服务 → 轮询 `/api/state`」的真冒烟，CI 双平台执行。
- **CI**：滚动与版本发布均构建自包含包；增加便携 Python 与 pip wheel 缓存（actions/cache）控制耗时与 macOS 10× 计费。
- **Windows GPU 说明**：PyPI 的 Windows torch 是 CPU 轮子（CUDA 版约 2.5 GiB，超过 GitHub 单资产限制，无法默认打进去）。默认包保证「双击即开网页、CPU 可跑」；新增 `tools/install_cuda_torch.py`（NVIDIA 用户可选执行一次，下载 CUDA 版 torch 进 `envs/web`）并在使用说明中说明。
- **文档**：使用说明改为「包内自带运行时，双击直接开网页；模型应用内下载」，补充 CUDA 加速说明与体积/平台要求；README 同步；评测/构建章节更新。
- **规格**：MODIFIED `one-click-packaging`——包内容新增自包含运行时与依赖、产物命名/冒烟、首启体验（不联网直接启动）、CI 构建；新增「自包含运行时」要求。

## Capabilities

### Modified Capabilities

- `one-click-packaging`：交付形态从「瘦源码包 + 首启 pip」改为「自带便携 Python 与依赖的自包含包，双击即开网页」；模型仍不随包、在应用内下载。

## Impact

- 修改：`packaging/build_package.py`、`packaging/smoke_package.py`、`packaging/launchers/start.command`、`packaging/launchers/start.bat`、`tools/start.py`、`web/server.py`、`.github/workflows/oneclick.yml`、`.github/workflows/oneclick-release.yml`、`packaging/使用说明.md`、`README.md`。
- 新增：`packaging/smoke_bundle.py`、`tools/install_cuda_torch.py`、`tests/test_bundle_layout.py`。
- 体积/成本：单包 mac ≈250–350 MB、win ≈250–300 MB；CI 每次构建多 1–3 分钟依赖安装（加缓存后更快），macOS runner 10× 计费仍需注意。
- 外部动作：push 后滚动 release 换新；发布 `v0.1.8` 正式版（两个自包含包）。
- 兼容性：`--with-models` 保持移除；模型渠道机制不变；本地开发仍可用 `--runtime slim` 或直接 `python tools/start.py`。

## 追加：Windows CUDA 加速套件（参考 ASRbox 的实现方式）

自包含包默认内置 **CPU 版 torch**（Windows）。为了让 NVIDIA 显卡用户获得 CUDA 加速而不把 2.5–3 GB 的 CUDA torch 打进主包（会超 GitHub 单资产 2 GiB 限制），本变更同时新增：

- **模型页新增 Windows 专属条目「CUDA 加速套件」**（`web/static` 的模型页，仅 Windows 显示）：显示 GPU 检测结果、下载进度（分卷/已下载字节）、安装状态（未安装 / 下载中 / 已安装待重启 / 已启用 / 失败原因），支持下载、取消（断点续传）、移除。
- **套件即 cu128 torch 树**：由独立 workflow（`cuda-kit.yml`，手动/tag `cuda-kit-*` 触发）在 windows runner 上构建：按锁定的 cu128 索引安装 torch → 裁剪（只留 `torch/` 与 dist-info、去掉 include/share/__pycache__）→ 逐文件 sha256 清单 → 可复现 zip → 切成 ≤1.9 GiB 的分卷 → 连同 `cuda-kit-manifest.json` 发布到独立 release `cuda-kit-cu128-torch2.10.0`（不随每次应用发布重复上传）。
- **服务端下载与安装管理器**（`web/cuda_kit.py`，参照 ASRbox `backend/services/cuda_kit.py` 的状态机/校验/注入思路）：读 manifest → 逐卷 Range 下载（续传、取消、进度）→ 校验 sha256 → 安全解压到 `web/data/cuda-kit/kit` → 校验逐文件哈希；启动时若套件就位，把 kit 目录注入 `sys.path`（Windows 额外 `os.add_dll_directory(torch/lib)`），让 `import torch` 命中 CUDA 版。
- **注入与生效**：进程启动时注入；下载完成提示「重启应用后生效」，并提供「移除套件」。
- **配置**：`tools/cuda_kit.json`（随包）固定 manifest URL 与预期 torch 版本；torch 版本不匹配时状态标为「需重新下载」。
- **文档**：Windows 用户说明「默认 CPU 可跑；NVIDIA 显卡建议安装 CUDA 加速套件（约 3 GB，模型页下载，重启生效）」。
- **规格**：ADDED `windows-cuda-kit` 能力。
