## Purpose

定义「一键包不含模型」前提下的模型下载渠道：国内镜像（hf-mirror.com）与国外直连（huggingface.co）两种渠道。首启引导（应用内）、模型页切换、命令行下载器共享同一份渠道设置，并规定端点解析优先级、启动器不下载模型、下载失败时的提示与切换方式。

## ADDED Requirements

### Requirement: 渠道定义

系统 MUST 只提供两种下载渠道，标识为 `mirror`（国内网络，端点 `https://hf-mirror.com`）与 `huggingface`（国外网络，端点 `https://huggingface.co`）。渠道标识 MUST 与既有设置项 `download_source` 的取值域一致，MUST NOT 引入第二套命名。

#### Scenario: 渠道与端点映射

WHEN 任一入口（应用模型页、命令行下载器、bootstrap）请求下载某组件并指定渠道 `mirror`
THEN 该下载经 `https://hf-mirror.com` 进行；指定 `huggingface` 时经 `https://huggingface.co` 进行

### Requirement: 渠道的单一真相与持久化

应用内切换、首启引导与命令行下载 MUST 读取/写入同一份持久化设置 `web/data/settings.json` 的 `download_source` 字段。文件缺失、缺该字段或取值非法时 MUST 按默认值 `mirror` 处理。写入 MUST 只影响写入之后发起的下载，MUST NOT 中断进行中的下载。

#### Scenario: 设置被各入口复用

WHEN 应用模型页把渠道切到「国际直连」并保存
THEN 之后运行 `python tools/hf_download.py core` 时无需任何参数也会经 `https://huggingface.co` 下载

#### Scenario: 缺失设置为默认镜像

WHEN `web/data/settings.json` 不存在或只有其他字段
THEN 所有入口按 `mirror` 行为执行，且不报错

### Requirement: 端点解析优先级

`tools/hf_download.py` MUST 支持 `--source {mirror,huggingface}` 与 `--endpoint URL` 参数。最终端点 MUST 按以下优先级解析（高到低）：`--endpoint` > `--source` > 环境变量 `YUE2_HF_ENDPOINT` > 已保存的 `download_source` > 默认 `mirror`。显式参数 MUST NOT 修改已保存设置。

#### Scenario: 显式参数覆盖已保存设置

WHEN 已保存渠道为 `mirror`，用户执行 `python tools/hf_download.py core --source huggingface`
THEN 该次下载经 `https://huggingface.co` 进行，且不修改已保存设置

#### Scenario: 环境变量保持既有语义

WHEN 未传 `--source` / `--endpoint` 且设置了 `YUE2_HF_ENDPOINT`
THEN 该次下载使用 `YUE2_HF_ENDPOINT` 指定的端点，优先于已保存设置

### Requirement: 首启只准备环境，模型在应用内下载

`tools/start.py` 首启 MUST 只准备环境（虚拟环境 + 依赖 + Apple Silicon 的 MLX 运行时），MUST NOT 触发任何模型下载。应用启动后若核心模型未安装，前端 MUST 自动进入「模型」页并提示「先下载核心模型，下载源可切换（国内镜像 / 国际直连）」；用户在该页完成渠道选择与下载。该引导 MUST 只使用既有视图切换与 toast 文案，MUST NOT 新增可见控件。

#### Scenario: 干净机器首启

WHEN 收件人首次双击启动器
THEN 启动器只安装环境并打开服务地址，页面停在「模型」页，提示下载核心模型（约 7.3 GiB）与可选下载源

#### Scenario: 缺核心模型时创建

WHEN 核心模型未安装时用户点击「创作」
THEN 应用切到「模型」页并提示先下载核心模型，不发起生成请求

### Requirement: 命令行下载的渠道选择

`tools/bootstrap.py` MUST 默认只准备环境；当显式要求下载模型（`--models`，或 `--extras` / `--transcribe` / `--mlx`）时：交互模式 MUST 询问下载渠道并持久化（已保存渠道时 MUST 沿用且不重复询问）；`--yes` MUST 使用已保存值或默认 `mirror` 且不提问；`--download-source {mirror,huggingface}` MUST 一次性覆盖且不落盘。

#### Scenario: 交互式安装询问渠道

WHEN 用户在终端运行 `python tools/bootstrap.py --models`
THEN 向导询问「1 国内网络 / 2 国外网络」，选择写入 `download_source`，随后按该渠道下载

#### Scenario: 无人值守安装

WHEN 以 `--yes --models` 或非 tty 场景运行
THEN 不出现交互提问，按已保存渠道（缺省 `mirror`）下载

#### Scenario: 已保存渠道不重复询问

WHEN 用户已选择过渠道后再次运行 `python tools/bootstrap.py --models`
THEN 向导打印已保存渠道并沿用，不再询问

### Requirement: 失败提示与切换

下载失败时系统 MUST 打印当前渠道、可切换的另一渠道与切换方法（命令行 `--source` 或应用模型页），并 MUST 保留已下载分片以支持续传。系统 MUST NOT 自动跨渠道重试。

#### Scenario: 渠道不可达

WHEN 选定渠道下载失败（HTTP 错误或超时）
THEN 输出包含当前渠道名与「换渠道重试」方法的提示，已落盘分片保留，重跑时从断点续传
