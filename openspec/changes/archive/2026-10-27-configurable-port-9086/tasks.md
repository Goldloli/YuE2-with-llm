# Tasks: 2026-10-27-configurable-port-9086

## 1. 端口解析与服务端

- [x] 1.1 `web/server.py`：新增 `_resolve_port()`（`--port` > `YUE2_PORT` > `9086`，非法值回退+告警）；`__main__` 用 argparse 接收 `--port` 并传给 `uvicorn.run`
- [x] 1.2 `tools/start.py`：新增 `resolve_port()`（同优先级，默认 9086）；`URL` / `wait_and_open()` 用解析结果；子进程环境注入 `YUE2_PORT`；打印实际地址
- [x] 1.3 启动器透传参数：`packaging/launchers/start.command` 追加 `"$@"`、`start.bat` 追加 `%*`

## 2. 测试

- [x] 2.1 新增 `tests/test_port_config.py`：默认值、env 覆盖、`--port` 覆盖、非法值回退、`server_env()` 注入 `YUE2_PORT`、两处解析一致

## 3. 文档与规格

- [x] 3.1 `README.md`：快速开始/源码运行里的地址改 9086，补 `YUE2_PORT` / `--port` 覆盖说明
- [x] 3.2 `packaging/使用说明.md`：启动地址改 9086；「端口被占用」FAQ 改为环境变量/参数示例
- [x] 3.3 `docs/ui-baseline/README.md`：截图服务地址改为默认端口 9086
- [x] 3.4 spec delta：MODIFIED「首启体验」（URL 9086）+ ADDED「本地服务端口」

## 4. 验证与发布

- [x] 4.1 `pytest` 全绿；`actionlint`
- [x] 4.2 重建本地 mac 包 + `smoke_package` / `smoke_bundle`；实测双击启动监听 9086
- [x] 4.3 push main → 滚动包 CI 全绿（新包默认 9086）
- [x] 4.4 打 `v0.1.9` → 双平台自包含包构建 + 真冒烟 + release 发布
- [x] 4.5 归档变更（`openspec archive`）
