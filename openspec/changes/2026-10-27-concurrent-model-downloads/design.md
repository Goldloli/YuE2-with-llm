# Design: 2026-10-27-concurrent-model-downloads

## Context

`web/server.py` 的 `DownloadManager` 只持有单个 `current` 任务：`start()` 遇到任何运行中的进程即抛 409，`snapshot()` 返回单个 dict，`_models_payload()` 用 `active["component"]` 匹配唯一在下载的组件。下载由 `tools/hf_download.py <mode>` 子进程执行（curl 分片、断点续传、sha256 校验）。

各组件目标权重路径（`MODEL_COMPONENTS[*].paths`）互不重叠：core（YuE2-3B、YuE2-Vae）、decoders（Vae-legacy、Vae-merge）、realaudio、loras、transcribe、mlx-8bit/bf16/4bit 各自独立目录。**唯一共享写目标**：MLX 各变体会写同一批 `YuE2-3B-MLX/` 下的代码与配置文件（`generate.py`、`convert.py`、`test_parity.py`、`yue2_model.py`、`yue2_vae.py`、`README.md`），由 `download_small()` 写入（当前实现：先 unlink 再 curl 直写目标，非原子）。

## Goals / Non-goals

**Goals**：不同组件可并发下载（上限 3）；同一组件不重复启动；并发下进度/错误/取消互相独立；共享小文件并发写安全；前端同时显示多行进度。

**Non-goals**：不做下载队列/优先级/限速；不允许同一组件多进程；不改下载源切换、断点续传、sha256 校验；不改 CUDA 套件自身的下载管理器；不做自动重试策略变更。

## Decisions

- **D1 jobs 字典**：`DownloadManager.jobs: dict[str, dict]`（key=component id），每个 job 保存 `component/mode/source/paths/proc/error/cancelled/started/log_tail`。
- **D2 启动校验顺序**：① 同 id 已有运行中任务 → 409（提示该组件已在下）；② 运行中任务数 ≥ `MAX_CONCURRENT_DOWNLOADS`(3) → 409；③ 与运行中任务的权重 `paths` 有交集 → 409（防御性）；④ 失败残留条目（proc=None）在同 id 重试时被替换。
- **D3 snapshot 与 payload**：`snapshot()` 返回列表（含 running 标记）；`_models_payload()` 先建 id→job 映射，逐组件填 `downloading/error`，payload 顶层新增 `downloads` 列表；`/api/state` 的 `download_active` 同步为列表。
- **D4 取消**：`cancel(component_id)` 只 terminate 该 job 的进程并标记 cancelled；watcher 退出时删除该 job；其他 job 不受影响。对失败残留条目取消则直接删除。
- **D5 原子小文件写**：`download_small()` 写入 `<name>.tmp-<pid>-<tid>`，成功且大小符合后 `os.replace(tmp, out)`；失败清理临时文件。这样两个 MLX 变体并发下载共享代码文件时，最终落盘内容一致且不会出现半截文件。
- **D6 前端零结构改动**：模型行渲染已按组件独立（`c.downloading`/`c.downloaded_bytes`/`c.error`），只需后端把多个组件同时标为下载中；完成 toast 已有逐组件逻辑。

## Risks

- 并发下载共享出口带宽 → 单个下载变慢；上限 3 避免进程/连接数爆炸。
- 共享小文件并发写 → 已用原子写 + 大小校验消除；大权重路径当前无重叠，仍保留互斥兜底。
- 旧客户端若消费 `download_active` 对象结构会不兼容 → 本仓库前端未使用该字段，接口语义变化仅影响内部轮询。

## Migration

无数据迁移；已下载分片继续有效；取消/断点续传行为不变。
