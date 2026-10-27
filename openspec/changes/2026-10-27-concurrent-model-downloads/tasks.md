# Tasks: 2026-10-27-concurrent-model-downloads

## 1. 后端并发下载

- [x] 1.1 `web/server.py` `DownloadManager`：`current` → `jobs: dict[id, job]`；新增 `MAX_CONCURRENT_DOWNLOADS = 3`；启动校验顺序 同 id 409 → 并发上限 409 → 权重路径重叠 409；`snapshot()` 返回活动列表；`cancel(id)` 只影响目标 job
- [x] 1.2 `web/server.py` `_models_payload()` / `/api/state`：按 id 映射活动任务，逐组件填 `downloading`/`error`；payload 新增 `downloads` 列表；`download_active` 改为列表

## 2. 下载器并发安全

- [x] 2.1 `tools/hf_download.py` `download_small()`：临时文件 + `os.replace` 原子落盘（失败清理临时文件），并发下载共享小文件（MLX 代码/配置）安全

## 3. 测试

- [x] 3.1 `tests/test_web_models.py`：改为并发语义——两个不同组件可同时启动、同组件重复 409、第 4 个 409（上限）、权重路径重叠 409、取消其一不影响另一个、snapshot 列表与 payload 多组件标记
- [x] 3.2 新增 `tests/test_hf_download_atomic.py`：小文件下载中途失败不产生半截目标文件（monkeypatch curl，无网络）

## 4. 文档与验证

- [x] 4.1 文档：README / `packaging/使用说明.md` 说明可同时下载（最多 3 个）
- [x] 4.2 `pytest` 全绿；`actionlint`；手动在应用内同时下载两个 MLX 变体，验证各自进度/取消/完成 toast

## 5. 打包与发布

- [ ] 5.1 push main → 滚动包 CI 更新
- [ ] 5.2 打 `v0.1.11` → 双平台自包含包构建 + 真冒烟 + 发布；重建本地 mac 包
- [ ] 5.3 归档变更
