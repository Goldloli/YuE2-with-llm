## MODIFIED Requirements

### Requirement: 首启体验

包内启动器 MUST 在启动时**不进行任何依赖安装或联网下载**：检测到包内 `runtime/` 时 MUST 直接以包内解释器启动本地服务并打开浏览器；仅当是开发用瘦包（无 `runtime/`）时才允许走原有的环境引导路径。应用检测到核心模型未安装时 MUST 自动进入「模型」页并提示下载核心模型（约 7.3 GiB），下载源 MUST 可在「国内网络（hf-mirror.com）」与「国外网络（huggingface.co）」之间切换，选择 MUST 持久化并供后续下载复用。使用说明 MUST 覆盖平台要求（macOS Apple Silicon / Windows x64）、包体积与磁盘要求、模型下载与渠道切换、可选组件、Windows GPU 可选升级（CUDA 版 torch）与常见问题（端口、镜像、环境重置）。

#### Scenario: 干净机器首启

WHEN 收件人在装有 macOS（Apple Silicon）或 Windows x64 的机器上解压并双击启动器
THEN 启动器不联网、不安装依赖，用包内运行时直接启动服务并打开 `http://127.0.0.1:9086`，页面停在「模型」页提示下载核心模型

#### Scenario: 首启选择国外渠道

WHEN 用户在「模型」页把下载源切到「国际直连」后下载核心模型
THEN 下载经 `https://huggingface.co` 进行，设置持久化为 `download_source=huggingface`

## ADDED Requirements

### Requirement: 本地服务端口

本地服务 MUST 默认监听 `127.0.0.1:9086`，且端口 MUST 可按优先级配置：命令行参数 `--port` > 环境变量 `YUE2_PORT` > 默认 `9086`。非法值（非整数或不在 1–65535 之内）MUST 回退到默认端口并给出告警，MUST NOT 崩溃。`web/server.py` MUST 支持 `python web/server.py --port <N>`；`tools/start.py` MUST 用同一个解析结果完成「探测就绪 / 打开浏览器 / 启动子进程」，并通过环境变量把端口传给服务进程。两个平台启动器 MUST 把额外参数透传给 `tools/start.py`，使一键包用户可直接 `start.command --port <N>` / `start.bat --port <N>`。服务 MUST 仅监听回环地址 `127.0.0.1`，MUST NOT 对外暴露。

#### Scenario: 默认端口

WHEN 用户直接双击启动器（未设置 `YUE2_PORT`，未传 `--port`）
THEN 服务监听 `127.0.0.1:9086`，浏览器打开 `http://127.0.0.1:9086`

#### Scenario: 环境变量覆盖

WHEN 以 `YUE2_PORT=9090` 启动服务
THEN 服务监听 `127.0.0.1:9090`，`tools/start.py` 打开 `http://127.0.0.1:9090`

#### Scenario: 命令行覆盖（一键包）

WHEN 在解压目录执行 `./start.command --port 9090`（Windows：`start.bat --port 9090`）
THEN 服务监听 `127.0.0.1:9090`，浏览器打开对应地址

#### Scenario: 非法端口回退

WHEN `YUE2_PORT=abc` 或传入 `--port 70000`
THEN 打印告警并以默认 `127.0.0.1:9086` 启动
