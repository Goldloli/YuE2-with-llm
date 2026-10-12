# Tasks: model-manager

## 1. 下载器扩展

- [x] 1.1 `tools/hf_download.py`：细粒度组件模式——`decoders`（legacy+merge）、`realaudio`、`lora-deathmetal`、`lora-jpop`、`lora-instrumental`、`mlx-bf16`、`mlx-4bit`（`extras`/`mlx`=8bit 保留向后兼容）；验证：`--help`/dry 模式列出全部模式
- [x] 1.2 小体积实测：`lora-jpop` 与 `realaudio` 下载到真实路径校验 SHA；验证：`python tools/hf_download.py realaudio` 正常完成（已装文件显示 skip）

## 2. 服务端

- [x] 2.1 模型清单：`GET /api/models`（组件 manifest + 状态 + 下载进度）；服务器重启后进度可恢复（依据落盘字节）
- [x] 2.2 下载通道：独立线程单并发 + `POST /api/models/download`（组件名/源校验、重复 409、可选组件前置检查）+ `POST /api/models/cancel`（终止进程、保留分片）；验证：curl 发起 realaudio 下载观察进度，取消后重发续传
- [x] 2.3 设置：`download_source`（mirror|huggingface，校验与持久化）+ `default_lora`（null|已安装 LoRA，校验）；`/api/state` 下发两字段
- [x] 2.4 服务端测试：组件名非法 422、源非法 422、下载中重复 409、cancel 未知任务 404、default_lora 非法值 422；`pytest` 全绿

## 3. 前端

- [x] 3.1 侧栏「模型」导航 + `#view-models` 容器 + `showView` 接线；验证：点击切换、选中态、创作面板隐藏
- [x] 3.2 页面渲染：下载源分段控件（持久化）、「默认设置」卡（引擎/变体/默认 LoRA）、分组清单（状态徽标 + 体积 + 下载/取消按钮 + 进度条）；轮询刷新（页面可见时）
- [x] 3.3 `default_lora` 接入创作流程：`applyPreferences` 预选（MLX 下清空）；验证：设置后新建表单预选、引擎切 MLX 清空
- [x] 3.4 i18n（约 35 条 en/zh)；验证：两语言无漏文案

## 4. 实测与基线

- [x] 4.1 浏览器端到端：切源 → 下载 realaudio（约 0.17 GB）→ 进度百分比 → 完成转「已安装」；中途取消再续传；生成一首歌验证下载并行不阻塞
- [x] 4.2 基线全量重截（5 页 × en/zh）+ 新增 models 页（× en/zh）；对照确认除侧栏新增项与新页面外零差异

## 5. 校验与归档

- [x] 5.1 `openspec validate model-manager --strict`；归档；`codegraph sync`
