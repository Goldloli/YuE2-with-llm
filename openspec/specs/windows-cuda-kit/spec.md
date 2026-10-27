# windows-cuda-kit Specification

## Purpose
定义 Windows 专属的可选「CUDA 加速套件」：自包含一键包默认内置 CPU 版 torch，NVIDIA 显卡用户可在应用「模型」页下载并安装一个独立的 cu128 torch 套件来启用 CUDA 加速；套件以独立 GitHub release（分卷 + manifest）分发，应用内完成校验、安装、注入与移除。

## Requirements

### Requirement: 套件定义与分发

CUDA 加速套件 MUST 为仅 Windows x64 可用的可选组件，MUST NOT 打进一键包主包（主包保持 CPU torch）。套件 MUST 由独立 workflow 在 windows runner 上构建：按锁定的 cu128 索引安装 torch（版本与应用主包 torch 主版本一致），裁剪为只含 `torch/` 与 `torch-*.dist-info`（去掉 `include`、`share`、`__pycache__`），生成逐文件 sha256 清单 `cuda-kit-manifest.json`（含 `schema_version`、`kit_version`、`torch_version`、`total_bytes`、`files[]`、`zip_sha256`、`parts[]`），并将套件 zip 切成每卷 < 2 GiB 的分卷。套件 MUST 发布在固定 tag `cuda-kit-cu128-torch<torch主版本>` 的 release（manifest + 分卷），MUST NOT 随每次应用发布重复上传。

#### Scenario: 构建并发布套件

WHEN 维护者触发套件构建 workflow（手动或 `cuda-kit-*` tag）
THEN 产出 `cuda-kit-manifest.json` 与 ≤2 GiB 的分卷，校验（拼接后 zip sha256、逐文件哈希）通过后发布到固定 tag 的正式 release

### Requirement: 模型页入口与状态

应用「模型」页 MUST 在 Windows 平台显示「CUDA 加速套件」条目（其他平台 MUST NOT 显示），条目 MUST 展示：NVIDIA 显卡检测结果、安装状态（`not_downloaded` / `downloading` / `ready`（已安装、重启后生效）/ `enabled`（当前进程已启用 CUDA）/ `invalidated`（torch 版本不匹配））、下载进度（已下载字节/总量、当前分卷）与失败原因。条目 MUST 支持下载、取消（保留已下载分卷以便续传）与移除。UI MUST 复用模型页既有卡片与进度条形态，MUST NOT 新增视觉组件形态。

#### Scenario: Windows 无 NVIDIA 显卡

WHEN Windows 用户打开模型页且 `nvidia-smi` 未检测到 NVIDIA 显卡
THEN 条目 MUST 显示「未检测到 NVIDIA 显卡」并禁用下载入口，但仍可见说明

#### Scenario: 下载与取消

WHEN 用户点击下载后中途取消
THEN 下载 MUST 停止且已下载分卷保留；再次点击下载 MUST 从已下载字节续传

### Requirement: 下载校验与安全

下载与安装 MUST 只接受 HTTPS 的 `github.com` release 资产（重定向仅允许 `*.githubusercontent.com`）；manifest 与分卷 MUST 校验 sha256，拼接后的 zip MUST 校验 `zip_sha256`；解压 MUST 拒绝绝对路径、`..` 与反斜杠路径；安装完成后 MUST 校验逐文件 sha256 与 manifest 一致。上述任一失败 MUST 中止安装、MUST NOT 留下可用 kit，并向用户显示原因。

#### Scenario: 分卷损坏

WHEN 任一分卷 sha256 与 manifest 不符
THEN 安装 MUST 失败并提示校验错误，已安装的 kit MUST 保持原状（不覆盖）

### Requirement: 注入与生效

应用进程启动时，若 kit 就位且其 torch 主版本与当前 torch 一致，MUST 在导入 torch 之前把 kit 目录注入 `sys.path`，Windows 上 MUST 同时把 `torch/lib` 加入 DLL 搜索目录；注入后 `torch.__file__` 指向 kit 视为已生效，且 MUST 通过 `torch.cuda.is_available()` 判断 CUDA 是否真实可用。安装完成但尚未重启时，界面 MUST 提示「重启应用后生效」。

#### Scenario: 安装后重启生效

WHEN 用户在模型页装好套件并重新启动应用
THEN 应用 MUST 在启动日志中标注 CUDA 加速套件已生效，模型页状态显示「已启用」，生成任务使用 CUDA 设备

### Requirement: 版本失效与移除

当 kit 的 `torch_version` 主版本与应用当前 torch 不一致时，状态 MUST 为 `invalidated` 并提示重新下载；用户移除套件时 MUST 删除 kit 与下载暂存目录（下载进行中时 MUST 拒绝移除），移除后重启应用 MUST 回退到 CPU torch。

#### Scenario: 应用升级后套件失效

WHEN 应用 torch 主版本变化且旧 kit 仍在
THEN 模型页 MUST 显示「套件已失效，请重新下载」，且应用 MUST NOT 注入旧 kit
