# Proposal: 2026-10-27-configurable-port-9086

## Why

默认服务端口 `127.0.0.1:7860` 与用户本机另一个常驻服务（Qwen 影像工作台）冲突：两者都要用 7860，无法同时运行；且端口在 `web/server.py`、`tools/start.py` 里硬编码，临时换端口只能改代码，一键包用户更无从调整。

用户要求把默认端口改为 **9086**，覆盖项目本体与两个平台的一键包。

## What Changes

- **默认端口改为 9086**（`http://127.0.0.1:9086`）：`web/server.py` 的 `uvicorn.run` 与 `tools/start.py` 打开/探测的地址全部改用新端口。
- **端口可配置**：解析优先级 `--port` 命令行 > `YUE2_PORT` 环境变量 > 默认 `9086`；非法值（非整数 / 越界）MUST 回退默认并告警，不得崩溃。
  - `python web/server.py --port 9090`、`YUE2_PORT=9090 python web/server.py`；
  - `python tools/start.py --port 9090`、`YUE2_PORT=9090 python tools/start.py` 探测/打开/启动用同一端口；
  - 两个平台启动器把额外参数透传给 `tools/start.py`（`start.command "$@"`、`start.bat %*`），一键包用户可 `./start.command --port 9090`。
- **文档**：`README.md`、`packaging/使用说明.md`、`docs/ui-baseline/README.md` 更新默认端口与覆盖方式（「端口被占用」FAQ 改为环境变量/参数示例）。
- **规格**：MODIFIED `one-click-packaging` 的「首启体验」（URL 改为 9086）；ADDED「本地服务端口」要求（默认 9086 + 三级配置 + 启动器透传 + 仅监听 127.0.0.1）。
- **发布**：push main 后滚动包 `oneclick-latest` 自动更新；正式版打 **v0.1.9**，双平台自包含包冒烟后发布；重建本地 mac 包供用户测试。

## Capabilities

### Modified Capabilities

- `one-click-packaging`：首启打开地址由 `http://127.0.0.1:7860` 改为 `http://127.0.0.1:9086`，并新增端口可配置（`--port` / `YUE2_PORT`）要求。

## Impact

- 修改：`web/server.py`、`tools/start.py`、`packaging/launchers/start.command`、`packaging/launchers/start.bat`、`README.md`、`packaging/使用说明.md`、`docs/ui-baseline/README.md`。
- 新增：`tests/test_port_config.py`。
- 兼容性：默认端口变化属**行为变更**（老书签需改 9086）；模型、下载渠道、CUDA 套件、包结构、UI 均不变。
- 外部动作：push 后滚动包换新；发布 `v0.1.9`；重建本地 mac 包。
