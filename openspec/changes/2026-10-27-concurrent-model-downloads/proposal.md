# Proposal: 2026-10-27-concurrent-model-downloads

## Why

模型下载目前是**单通道**：只要任一组件的下载进程在跑，再点其他组件下载就返回 409，页面弹「A download is already running (mlx-8bit)」。用户想同时下载多个组件（例如 MLX 8-bit 和 4-bit 一起下、或一边下核心模型一边下 LoRA），当前实现做不到。

## What Changes

- **下载管理器支持并发**（`web/server.py` `DownloadManager`）：
  - 由「单 `current`」改为「按组件 id 的 jobs 字典」，不同组件可同时下载；
  - 并发上限 `MAX_CONCURRENT_DOWNLOADS = 3`（超过时 409 并提示等待一个完成）；
  - 同一组件重复发起仍 409（不产生第二个进程）；
  - 目标**权重文件**与任一在跑任务重叠时 409（防御性互斥，当前组件之间权重路径均不重叠）；
  - `snapshot()` 返回活动任务列表；每个任务的进度、错误、取消互相独立。
- **接口状态并发化**：`GET /api/models` 中每个组件独立给出 `downloading` / `downloaded_bytes` / `error`，并新增 `downloads` 活动列表；`GET /api/state` 的 `download_active` 改为列表。
- **下载器并发安全**（`tools/hf_download.py`）：小文件下载改为**原子写**（先写临时文件再 `os.replace`），消除并发下载共享小文件（MLX 各变体会共享 6 个代码/配置文件）时的互相覆盖竞争；大权重文件仍由重叠校验 + 分片续传保证。
- **前端**：无需改结构——模型行本来就按组件独立渲染进度/取消/错误；本次让它同时显示多行进度、逐个完成 toast，并验证切换/取消互不影响。
- **规格**：MODIFIED `model-management`「下载通道与进度」「取消与续传」；ADDED「并发下载与互斥」。
- **发布**：push main 更新滚动包；打 `v0.1.11` 发布双平台正式包；重建本地 mac 包。

## Capabilities

### Modified Capabilities

- `model-management`：下载通道由「单并发」改为「最多 3 个组件并发 + 同组件互斥 + 权重路径互斥」，取消只影响目标任务。

## Impact

- 修改：`web/server.py`、`tools/hf_download.py`、`README.md`、`packaging/使用说明.md`。
- 测试：`tests/test_web_models.py`（改为并发语义）、新增 `tests/test_hf_download_atomic.py`。
- 兼容性：接口字段增量兼容（`downloads` 新增，`download_active` 由对象变列表，前端未消费旧字段）；下载源、续传、sha256 校验、CUDA 套件逻辑不变。
- 外部动作：滚动包更新；发布 `v0.1.11`；重建本地 mac 包。
