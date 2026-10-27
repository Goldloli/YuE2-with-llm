# Design: 2026-10-27-self-contained-oneclick-bundle

## Context

- 现状：`build_package.py --platform …` 产出约 9 MB 的瘦源码包；`start.command` / `start.bat` → `tools/start.py` → 缺环境时跑 `bootstrap.py --yes --skip-models`，**第一次启动要联网 pip 安装依赖（约 1–2 GiB）**，随后才起服务。模型不随包，由应用内「模型」页下载（已有国内/国际渠道）。
- 参照内部项目的形态：`packaging/build_macos.sh` 下载 python-build-standalone（PBS）解出 `runtime/`，再 `pip install --target envs/<层>` 装依赖，启动器直接用包内 runtime，免安装、离线启动。
- 体积实测（PyPI / GitHub API 查询）：PBS cpython 3.11 stripped 包 mac 25.5 MB / win 24.0 MB；torch 2.10.0 mac arm64 75.7 MB、win64 108.5 MB；transformers 11.4 MB、numpy 13.7 MB、tokenizers 7.3 MB、torchaudio ~1 MB；mac MLX 0.6 MB + mlx-metal 42.9–74.5 MB（arm64 macOS ≥14）。估算 zip：mac 250–350 MB、win 250–300 MB，均低于 GitHub 单资产 2 GiB。

## Goals / Non-Goals

**Goals:**

- 双击启动器 → **不联网、不 pip**，数秒内打开 `http://127.0.0.1:7860`（模型下载仍在应用内，与现状一致）。
- 包内自带便携 Python + 全部运行依赖；MLX、音频转录所需的解释器路径全部走包内环境，不再依赖用户机器上的 Python/venv。
- CI 双平台构建、冒烟（真起服务）与 tag 发布；保留瘦包模式供开发快速验证。

**Non-Goals:**

- 不把模型打进包（用户已定：模型可下载，国内/国际渠道）。
- 不引入安装器（.dmg/.pkg/.exe）；仍是解压 + 双击。
- 不做 Intel Mac / Linux 包。
- 不把 CUDA 版 torch 默认打进 Windows 包（超 GitHub 单资产限制），改为可选一键升级脚本。

## Decisions

### D1：便携运行时 = python-build-standalone（PBS）

固定 `PBS_TAG` / `PBS_VERSION`（如 20261026 / 3.11.18），下载 `install_only_stripped` 的 `aarch64-apple-darwin` / `x86_64-pc-windows-msvc` 包，解到包内 `runtime/`。缓存目录可用 `YUE2_ONECLICK_CACHE` 覆盖（本地 `~/Library/Caches/yue2-oneclick`；CI 用 `actions/cache`）。

### D2：依赖布局 `envs/web` + `envs/mlx`

- `envs/web`：由 pyproject 的 dependencies + `[web]` extras + `torchaudio`（与 torch 同钉版）生成安装列表，`runtime/bin/python3 -m pip install --target envs/web …`（`PYTHONNOUSERSITE=1`）。应用与 SheetSage2 转录共用这一份（转录脚本只需要 torch/torchaudio/transformers/safetensors/numpy/soundfile）。
- `envs/mlx`（仅 macOS arm64）：`mlx` + `mlx-metal` + `tiktoken` + `numpy` + `soundfile`，供 MLX 推理脚本使用。
- 运行时依赖以 `--target` 平铺安装，避免任何 venv/pyvenv.cfg，整包可任意搬移。

### D3：启动器与 `tools/start.py`

- `start.command` / `start.bat`：若存在 `runtime/`（且 `envs/web` 在位），设置 `PYTHONPATH="envs/web:src"`，用包内解释器启动 `tools/start.py --bundled`；否则回退现有逻辑（调用系统 Python 的 `tools/start.py`，瘦包开发场景）。
- `tools/start.py --bundled`（或检测到 `runtime/`）：跳过一切环境准备，直接以包内解释器启动 `web/server.py` 并打开浏览器；`env_ready()` 不再涉及 `.venv`。
- 保留 `bootstrap.py` 与 `--runtime slim` 产物，供仓库开发者与快速验证。

### D4：服务端解释器解析（`web/server.py`）

- 新增「bundled 检测」：`runtime/` 存在时，MLX 与转录分别使用 `runtime/bin/python3`（win: `runtime/python.exe`）+ `PYTHONPATH=envs/mlx` / `envs/web` 启动子进程；
- 否则沿用现有 `.venv-mlx` / `.venv-sheetsage2` 路径；
- `mlx_available()` / `transcribe_available()` 与下载/生成路径都走该解析，避免硬编码 venv 路径。

### D5：构建流程（`build_package.py --runtime bundle|slim`）

bundle 模式顺序：暂存源码（现有逻辑）→ 解压 PBS 到 `runtime/` → `pip install --target envs/web` →（mac）`pip install --target envs/mlx` → 自检：
1. `runtime/bin/python3 -c "import torch, transformers, fastapi, uvicorn, soundfile"`（PYTHONPATH=envs/web）；
2. `runtime/bin/python3 -c "import sys; sys.path.insert(0,'src'); import yue2"`；
3. 条目红线（无 `models/`、`.venv*`、`web/data/`、`outputs/`；只含本平台启动器）。
然后打包 zip，校验体积 < 1.9 GiB。`--runtime slim` 保持现有行为（用于快速本地/开发验证）。

### D6：冒烟（真起服务）

- `smoke_package.py`：自包含包 MUST 含 `runtime/`（对应平台解释器）与 `envs/web/`（抽样关键包目录如 `torch/`、`fastapi/`），原有红线不变。
- 新增 `packaging/smoke_bundle.py`：解压到临时目录 → 用包内解释器 `import` 关键依赖 → 启动 `web/server.py`（随机空闲端口）→ 轮询 `/api/state` 断言返回 `core_installed` 等字段 → 关闭进程。CI 双平台在构建后执行（Windows 也用 Python 实现，避免 pwsh 分支）。
- 该冒烟直接验证「双击即用」：不需要网络、不需要用户 Python。

### D7：Windows GPU（CPU 默认 + 可选 CUDA）

PyPI 的 `torch` win 轮子是 CPU 版；CUDA 轮子约 2.5 GiB，超过 GitHub 单资产 2 GiB，无法默认内嵌。默认包保证启动与 CPU 运行；新增 `tools/install_cuda_torch.py`：检测 NVIDIA → `runtime\python.exe -m pip install --no-deps --upgrade --target envs\web torch --index-url https://download.pytorch.org/whl/cu128`，README/使用说明标明「NVIDIA 用户可选、一次约 2.5 GiB」。

### D8：CI 与缓存

两个 workflow 的构建步骤改为默认 bundle 模式；加 `actions/cache`：① PBS tarball（按 PBS 版本/平台），② pip wheel 缓存（按 `pyproject.toml` 哈希）。macOS 10× 计费提示保留；单腿预计 4–7 分钟（缓存命中约 2–4 分钟）。

### D9：体积与上限

构建后打印 zip 体积；`smoke_package.py`/构建脚本断言 < 1.9 GiB（GitHub 单资产 2 GiB 的余量）。当前估算 mac ≈ 250–350 MB、win ≈ 250–300 MB。

## Risks / Trade-offs

- [包体积从 9 MB 涨到 250–350 MB，Release 上传/下载变慢] → GitHub 单资产上限内；使用说明写明体积；rolling 与 tag 发布各上传一次。
- [CI 构建时间与 macOS 10× 计费增加] → PBS+wheels 缓存；单次构建 2–7 分钟，可控。
- [Windows CPU torch 无法 CUDA 加速] → 明确文档与一键升级脚本；不默认内嵌 CUDA（受资产上限约束）。
- [PBS / 依赖版本漂移] → PBS 版本钉死在脚本常量；依赖以 pyproject 钉版为准（torch/transformers 等有 == 版本）；构建日志记录实际安装版本。
- [包内 runtime 无法在某些 macOS 版本运行] → PBS 官方支持 macOS ≥11；使用说明注明 Apple Silicon / macOS 版本要求。
- [搬移包后路径失效] → 全部使用相对路径（启动器 `cd "$(dirname "$0")"`），`envs` 用 PYTHONPATH 注入，不写绝对路径。

## Migration Plan

1. 构建器支持 `--runtime bundle`（默认）与 `slim`，含自检与体积上限。
2. 启动器 + `tools/start.py` + `web/server.py` 适配包内运行时。
3. `smoke_bundle.py` 真冒烟；CI 接入双平台。
4. `tools/install_cuda_torch.py` + 文档。
5. 本地构建 mac bundle + 冒烟 + 交付测试；`pytest`/`actionlint`/`openspec validate`；push 后滚动 CI 冒烟；发布 `v0.1.8`。
6. 归档变更。

## Open Questions

- 无（用户已明确：依赖自带、双击直接开网页、模型仍应用内下载）。


## 追加设计：Windows CUDA 加速套件（对齐 ASRbox）

### Context: ASRbox 的做法（已通读）

- `scripts/build-cuda-kit.py`：`pip install --target kit-root -r requirements-windows-cuda.lock`（cu128）→ 裁剪只留 `torch/` + `torch-*.dist-info`、删 `include`/`share`/`__pycache__` → 生成逐文件 sha256 manifest（schema_version/kit_version/torch_version/python/platform/file_count/total_bytes/files）→ 固定时间戳的可复现 zip → 按 `--parts` 切字节分卷（每卷 <2 GiB）并在 manifest 里记录 `zip_name/zip_size/zip_sha256/parts[]`；附 `--check`、`--verify-parts` 自检。
- 资产发布到应用 release（`v{version}`），后端 `backend/services/cuda_kit.py` 负责：manifest 校验（HTTPS + github.com 白名单）、逐卷 Range 下载（续传/取消/进度/每卷 sha256）、拼接校验 zip、安全解压（拒绝绝对路径/`..`/反斜杠）、逐文件哈希校验、`runtime/cuda-kit/` 目录管理（config.json 开关、state.json 断点状态恢复）、`nvidia-smi -L` 探测、状态机（not_downloaded/downloading/ready/enabled/enable_failed/invalidated）、版本不匹配失效。
- 注入：`ASRBOX_CUDA_KIT_DIR` 环境变量 + `pyi_rth_cuda_kit`/`_maybe_inject_cuda_kit`：`sys.path.insert(0, kit_dir)` + meta_path finder 兜住 frozen PYZ 里的 torch + Windows `os.add_dll_directory(torch/lib)`。
- UI：设置页面板（开关/下载/取消/删除/重试/进度分卷/详情），e2e 覆盖。

### yue 的适配决策

- **D10 套件资产独立成 release**：torch 在 pyproject 里钉死 2.10.0，套件与具体应用版本无关，因此用固定 tag `cuda-kit-cu128-torch2.10.0` 单独发布（workflow dispatch / `cuda-kit-*` tag 触发），避免每次滚动/正式发布都上传约 3 GB。`tools/cuda_kit.json` 记录 manifest URL；应用只校验 manifest 的 `torch_version` 与本地 torch 主版本一致。
- **D11 入口放模型页**：新增 `#view-models` 中的 Windows 专属条目（`MODEL_COMPONENTS` 里加 `platform="win32"` 的 `cuda-kit`，由 `_models_payload` 注入运行时状态字段），复用现有 `.mdl-*` 卡片/进度条样式，不新增视觉组件形态。
- **D12 状态简化**：与 ASRbox 相同的状态机子集——`not_downloaded / downloading / ready(已安装待重启) / enabled(已生效) / invalidated(版本不匹配)`；`enable/disable` 不单列开关（安装即启用、移除即停用），降低 UI 复杂度；GPU 检测用后台线程 `nvidia-smi -L`（仅 win32）。
- **D13 注入时机**：`web/server.py` 顶部在导入任何 torch 之前调用 `cuda_kit.maybe_inject()`（sys.path 前插 + add_dll_directory）；`torch.__file__` 指向 kit 即视为生效；已生效但 `torch.cuda.is_available()` 为假时状态显示失败原因。
- **D14 安全**：manifest/分卷 URL 限 HTTPS + `github.com` 白名单（重定向允许 `*.githubusercontent.com`）；解压拒绝绝对路径/`..`/反斜杠；逐卷与 zip、逐文件 sha256 校验；下载/解压在后台线程，支持取消并保留已下载分卷。
- **D15 套件构建流水线**：`packaging/cuda-requirements-win.txt`（torch==2.10.0）+ `packaging/build_cuda_kit.py`（裁剪/清单/复现 zip/分卷/自检）+ `.github/workflows/cuda-kit.yml`（windows runner，dispatch 或 tag，产出分卷 + manifest 后用 `gh release` 发布草稿→正式）。
