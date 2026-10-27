# Design: 2026-10-27-configurable-port-9086

## Context

现状端口硬编码：`web/server.py` 末尾 `uvicorn.run(app, host="127.0.0.1", port=7860)`；`tools/start.py` 常量 `URL = "http://127.0.0.1:7860"`，且 `wait_and_open()` 固定探测 7860。启动器只执行 `exec python tools/start.py --bundled`，无法传端口。冒烟脚本 `packaging/smoke_bundle.py` 自带随机空闲端口起 uvicorn，不依赖默认值。

用户机器 7860 被 Qwen 影像工作台占用（实测 PID 51815 监听 127.0.0.1:7860），7861/7897/8788 等也已被其他服务占用；9086 当前空闲。

## Goals / Non-goals

**Goals**：默认端口 9086；命令行/环境变量覆盖；一键包用户同样可覆盖；文档、规格、测试同步。

**Non-goals**：不改为 `0.0.0.0` 对外监听（仍仅 `127.0.0.1`）；不做端口自动探测/自动换端口；不改 UI；不改模型下载与 CUDA 套件逻辑；不改冒烟脚本的随机端口策略。

## Decisions

- **D1 解析优先级**：`--port` > `YUE2_PORT` > `9086`。临时覆盖用参数，长期覆盖用环境变量。
- **D2 双处独立解析**：`tools/start.py` 提供 `resolve_port()`；`web/server.py` 提供等价的 `_resolve_port()`（不 import tools，避免打包路径耦合）。非法值打印 warning 并回退默认。
- **D3 端口传递**：`tools/start.py` 解析后通过子进程环境 `YUE2_PORT=<port>` 传给 `web/server.py`，保证「探测端口 = 实际监听端口」；`web/server.py` `__main__` 用 argparse 接收 `--port`，缺省读 env。
- **D4 启动器透传**：`start.command` 追加 `"$@"`、`start.bat` 追加 `%*`；保留原 `--bundled` 行为。
- **D5 默认地址**：`http://127.0.0.1:9086`。
- **D6 测试**：`tests/test_port_config.py` 覆盖默认值、env、CLI、非法回退、`server_env()` 注入、两处解析一致；`smoke_bundle` 继续使用随机空闲端口。

## Risks

- 旧文档/书签/用户习惯里的 7860 失效 → README 与使用说明显式标注「默认端口已改为 9086」。
- 若用户机器 9086 也被占用 → 环境变量/参数可覆盖，FAQ 提供示例。
- 归档文档中的 7860 属历史记录 → 保持原貌，只更新当前规格与用户文档。

## Migration

无数据迁移，`web/data` 不受影响；一键包用户换新包即得新默认端口。
