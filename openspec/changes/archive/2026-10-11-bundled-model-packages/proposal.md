# Proposal: bundled-model-packages

## Why

现有构建只产出「通用 bootstrap 包」（不含模型，首启下载 7.3 GiB 模型）。用户要求一键包**内嵌模型**并按平台区分：**macOS 版包含全部模型**（torch + MLX + 全部扩展），**Windows 版包含全部 torch 模型**（不含 MLX）。目标用户拿到包即可离线开箱（依赖仍需联网安装，模型不再下载）。

## What Changes

（无视觉变更；构建体系与使用说明更新）

### 1. 平台化构建

`packaging/build_package.py` 增加 `--platform {macos,win-x64}`：

| | macOS 包 | Windows 包 |
|---|---|---|
| 内含模型 | **全部**：YuE2-3B、YuE2-Vae、Vae-legacy、Vae-merge、YuE2-3B-MLX（8bit+bf16）、MERT-v2-FullSong、SheetSage2、loras、YuE2-Realaudio（约 23 GB） | **全部 torch 模型**：以上除 `YuE2-3B-MLX`（约 12.4 GB） |
| 命名 | `yue2-studio-oneclick-macos-applesilicon-<YYYYMMDD>.zip` | `yue2-studio-oneclick-win-x64-<YYYYMMDD>.zip` |
| 输出目录 | `oneclick-packages/macos/` | `oneclick-packages/win-x64/` |

（平台子目录对齐参考项目。）

### 2. 打包实现要点

- **模型不再进暂存目录**：源码照旧白名单暂存；zip 阶段直接把 `models/` 下所需目录以 `STORED`（免压缩——权重不可压缩，STORE 既快又避免翻倍 IO）写入归档，其余文件 `DEFLATED`；
- zip64 自动启用（单文件最大 6.8 GB）；
- 反扫相应调整：平台包中 `models/` **允许**，`.venv*`、`outputs/`、`web/data/`、`.git`、`.env` 等仍禁止；
- 包内自检增加平台断言：macOS 包须含 `YuE2-3B`、`YuE2-Vae`、`YuE2-3B-MLX/8bit`、`YuE2-Realaudio`；Windows 包须含 `YuE2-3B`、`YuE2-Vae` 且**不含** `YuE2-3B-MLX` 目录；
- 旧的通用包（`oneclick-packages/yue2-studio-oneclick-20261011.zip` 9.6 MiB）删除，由平台包取代。

### 3. 首启体验与文档

- `tools/bootstrap.py` 已幂等（`models_ready()` 检测跳过下载）——包内模型会被自动识别，首启只创建虚拟环境并安装依赖（torch 等约 1–2 GiB 仍需联网，经镜像）；
- `packaging/使用说明.md` 更新：首启流程改为「建环境 → 装依赖 →（模型已随包）→ 启动」；补充磁盘要求（macOS 解压后 ≈28 GB、Windows ≈17 GB 含环境）与 Windows 解压工具提示（zip64 大包建议 7-Zip）；说明包体积来源与 MLX 仅 macOS 含。

### 4. 非目标

- 不内嵌依赖（torch 三套环境仍首启安装）——用户只要求模型；
- 不内置便携 Python（维持 bootstrap 形态）；
- 不在包内放 4bit 变体（本机未转换；需要时 `convert.py --bits 4` 后重建）。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `one-click-packaging`: 构建契约扩展——平台化（macos/win-x64 子目录与平台命名）、模型内嵌规则（mac 全模型 / win 全 torch 模型）、zip 压缩策略（模型 STORED）、平台断言自检。

## Impact

- **代码**：`packaging/build_package.py`（平台参数、直写 zip、反扫/自检调整）、`packaging/使用说明.md`、`.gitignore`（平台目录 `.gitkeep` 例外）；
- **产物**：`oneclick-packages/{macos,win-x64}/` 两个大包（≈23 GB / ≈12.4 GB，未压缩权重为主）；旧通用包删除；
- **磁盘**：构建暂存仅源码（模型直写）；产物目录合计 ≈36 GB（当前可用 1.5 TB）；
- **风险**：大文件 zip 的跨平台解压（zip64 在 Win10+ 资源管理器可用，说明中给 7-Zip 兜底）；构建耗时（IO 为主，分钟级）。
