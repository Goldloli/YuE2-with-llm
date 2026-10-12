# Tasks: fix-scroll-reset

- [x] 1.1 `renderModelsPage`：无变化跳过重建 + 重建时保留/恢复 `.mdl-scroll` scrollTop；验证：复现脚本（滚底 → 2.2s → 位置不变）
- [x] 1.2 `renderDetail`：同 id 软刷新保留 `#detail-content` scrollTop；切歌重置到顶；验证：生成中浏览歌词位置稳定、换歌回顶
- [x] 1.3 `openSettings`：重建时保留/恢复 `#modal` scrollTop；验证：滚到底点任一设置项不跳顶
- [x] 2.1 浏览器回归三场景；`openspec validate fix-scroll-reset --strict`；归档；`codegraph sync`
