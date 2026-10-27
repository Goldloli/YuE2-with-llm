## Purpose

定义「内嵌模型的一键包」在 GitHub CI 上的分档、构建、分卷与发布行为：收件人按机器配置选一个档位，下载分卷合并后即可开箱生成音乐，无需首启联网下载模型。

## ADDED Requirements

### Requirement: 模型包分档定义

模型包 MUST 按平台与大小分档，档位与内容 MUST 如下（各档均含 slim 包全部源码、双平台启动器与使用说明）：

- macOS（Apple Silicon）：
  - `mini`：`YuE2-3B-MLX/4bit`（含该档自带 VAE 与配置）+ `YuE2-Vae`，MUST NOT 含 torch `YuE2-3B`、MLX 其他档位、转录栈与 LoRA；
  - `standard`：`YuE2-3B-MLX/8bit` + `YuE2-Vae`，排除项同 `mini`；
  - `full`：`models/` 全部内容（torch `YuE2-3B`、MLX 三档、全部 VAE、`YuE2-Realaudio`、`loras/`、`MERT-v2-FullSong`、`SheetSage2`）。
- win-x64：
  - `standard`：torch `YuE2-3B` + `YuE2-Vae`（core），MUST NOT 含任何 `YuE2-3B-MLX/` 条目、转录栈与 LoRA；
  - `full`：全部 torch 系模型（`YuE2-3B`、全部 VAE、`YuE2-Realaudio`、`loras/`、`MERT-v2-FullSong`、`SheetSage2`），MUST NOT 含任何 `YuE2-3B-MLX/` 条目。

产物 zip MUST 命名为 `yue2-studio-oneclick-<平台标签>-<档位>-<YYYYMMDD>.zip`（平台标签沿用 `macos-applesilicon` / `win-x64`）。沿用 slim 包全部红线：MUST NOT 含 `.git*`、`.venv*`、`outputs/`、`web/data/`、`openspec/` 等；构建前 MUST 校验 `docs/style-terms.md` 与源词表同步；模型权重 MUST 以 STORED 写入且归档为 zip64。

#### Scenario: 档位内容边界

WHEN 构建 `macos` / `mini` 档
THEN zip 内含 `YuE2-3B-MLX/4bit/model.safetensors` 与 `YuE2-Vae/model.safetensors`，且不含 `YuE2-3B/model.safetensors`、`YuE2-3B-MLX/8bit/`、`MERT-v2-FullSong/` 任何条目

#### Scenario: Windows 平台排除 MLX

WHEN 构建 `win-x64` 任一档
THEN zip 内不存在任何 `YuE2-3B-MLX/` 前缀条目

#### Scenario: 红线与词表沿用

WHEN 构建任一档位
THEN 词表过期或包内出现 `.venv`、`web/data/`、`.git/` 任一时构建以非零码失败，不产出 zip

### Requirement: CI 现场下载与流式打包

CI 构建 MUST 在 runner 上现场下载模型：复用 `tools/hf_download.py` 的下载与 sha256 校验能力，CI 环境 MUST 设置 `YUE2_HF_ENDPOINT=https://huggingface.co`（直连，不走 hf-mirror）。下载 MUST 逐模型组件进行，组件下载完成并通过校验后 MUST 立即以 STORED 追加进 zip 并删除该组件的原始文件，使磁盘峰值 ≈ zip 体积 + 单个最大组件体积。构建开始前 MUST 检查 runner 可用磁盘（`df`），不足该档预估需求时 MUST 快速失败并打印需求与余量。构建 MUST 在 macOS 与 Windows runner 上均可运行（路径与换行自适应）。

#### Scenario: 流式打包控制磁盘峰值

WHEN 构建 `win-x64` / `full` 档（约 12.4 GB）
THEN 任一时刻磁盘占用不超过「zip 当前体积 + 正在下载的单个组件体积 + 1 GiB 余量」，构建完成后 runner 上不留模型原始文件

#### Scenario: 磁盘不足快速失败

WHEN 构建前可用磁盘低于该档预估需求
THEN 构建以非零码失败并打印预估需求与实际余量，不开始下载

#### Scenario: 下载校验

WHEN 任一模型文件下载完成
THEN 按其 `weights_manifest.json` 的 sha256 校验（无清单的文件按声明大小校验），校验失败即构建失败

### Requirement: 分卷切分与合并

超过 2 GiB 的产物 zip MUST 切分为 ≤1.9 GiB 的有序分卷（命名 `<zip名>.part-aa`、`.part-ab`……），每个分卷 MUST 附 sha256（汇总为单一 `<zip名>.sha256` 清单文件，格式 `<hash>  <文件名>`，逐行覆盖全部分卷）。合并方式 MUST 为跨平台通用：macOS/Linux `cat`、Windows `copy /b`，合并所得文件与原始 zip 字节一致。使用说明 MUST 覆盖分卷合并步骤、sha256 校验命令与各档位的内存/磁盘要求。

#### Scenario: 分卷产出

WHEN 构建产物 zip 为 12.4 GB
THEN 产出 7 个 ≤1.9 GiB 分卷与一个 sha256 清单，`cat` 合并后的文件 sha256 等于构建机上的 zip sha256

#### Scenario: 合并可用性

WHEN 收件人按使用说明在 Windows 上 `copy /b` 或在 macOS 上 `cat` 合并分卷
THEN 得到的 zip 可被系统解压工具正常打开，sha256 与清单一致

### Requirement: 触发与发布流

模型包 MUST NOT 随 push 触发。触发方式 MUST 为两种：

1. tag `models-v*`：先建**草稿** release（title 含 tag 与日期），macOS 与 win-x64 构建任务**并行**执行（各自构建该 tag 指定的档位集合），全部成功并上传分卷后 MUST 自动将草稿转为正式 release；任一任务失败时 release 保持草稿，收件人不可见半成品。
2. `workflow_dispatch`：手动选择平台与档位（或「全部」），产物上传至滚动 release `oneclick-models-latest`（同名资产替换，不堆积）。

冒烟失败 MUST 阻断上传与发布。release 资产 MUST 包含全部分卷与 sha256 清单。

#### Scenario: tag 正式发布流

WHEN 推送 tag `models-v1` 且双平台构建、冒烟、上传全部成功
THEN 该 tag 的 release 由草稿转为正式，含双平台全部档位分卷与清单

#### Scenario: 半成品不可见

WHEN 双平台任务任一失败
THEN release 保持草稿状态，外部访问该 tag 的 release 页面返回未发布

#### Scenario: 手动滚动发布

WHEN 以 `workflow_dispatch` 选择 `macos` / `standard` 运行成功
THEN `oneclick-models-latest` 内对应资产被替换为本期分卷与清单，其余平台/档位资产不受影响

### Requirement: 模型包冒烟

每个档位产物 MUST 经冒烟验证后方可上传：基于 zip 条目清单（不全量解压）校验该档必需模型条目在位（含 STORED 与声明大小）、禁用条目缺席（平台排除项、`.venv`、`web/data/` 等红线）、分卷数量与单卷大小上限合规；并 MUST 校验 sha256 清单与分卷一一对应。冒烟 MUST 在 macOS 与 Windows runner 上均可运行。

#### Scenario: 条目级冒烟

WHEN 冒烟检查 `macos` / `standard` 档产物
THEN zip 条目清单含 `YuE2-3B-MLX/8bit/model.safetensors`（STORED、大小 4264488042）且不含 `YuE2-3B/` 与 `YuE2-3B-MLX/4bit/` 前缀条目

#### Scenario: 分卷与清单一致性

WHEN 冒烟检查分卷产物
THEN 每个分卷 ≤1.9 GiB、命名有序连续，sha256 清单一行对应一个分卷且无遗漏
