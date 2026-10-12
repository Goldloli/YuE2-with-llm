# Tasks: repo-cleanup

## 1. 删除可再生文件

- [x] 1.1 `rm -rf .playwright-mcp .pytest_cache .cache` + 全仓 `find -name __pycache__ -exec rm -rf` + `.DS_Store` + `src/yue2_infer.egg-info`；验证：`ls -la` 根目录无缓存目录，pytest 重跑可再生成
- [x] 1.2 `.gitignore` 补 `.playwright-mcp/`；验证：`git status` 不再列出该目录

## 2. 清理一次性产物与孤儿记录

- [x] 2.1 删除 `outputs/comparisons/`、`outputs/zh-style-test/`；验证：`outputs/` 与 library 对照无孤儿目录（uploads 除外）
- [x] 2.2 从 `web/data/library.json` 删除孤儿记录 `brutal-test-2-lora-790`；验证：`/api/songs` 不再返回该条目

## 3. 归位

- [x] 3.1 `ref-suno-home.png`、`ref-suno-signin.png` → `ref-suno/`；验证：根目录无散落 png
- [x] 3.2 `requests/ink_moonlight.json` → `examples/ink_moonlight.json`，删除空 `requests/`；验证：`examples/` 含该文件
- [x] 3.3 `START.md` 移交 `packaging/使用说明.md`（在 oneclick-packaging 变更中执行，本变更只删根目录源文件）；验证：根目录无 START.md

## 4. 校验

- [x] 4.1 全量 `pytest` 绿色；`openspec validate repo-cleanup --strict`；归档；`codegraph sync`
- [x] 4.2 根目录复核：对照「保留清单」（compare/ ref-suno/ outputs/ models/ web/ docs/ openspec/ …）确认零误删
