# Tasks: fix-engine-default-toggle

- [x] 1.1 模型页引擎 seg：活动态改用 `s.default_backend`；sig 以 `s.default_backend` 参与判定；点击保存后调用 `setBackend` 同步会话并重建；验证：点击即时迁移 + pill 同步 + 持久化
- [x] 1.2 设置页通用 seg 处理器：`default_backend` 保存后同步会话；验证：设置页切换同样即时生效
- [x] 1.3 浏览器回归两页四向切换（torch↔mlx）+ MLX 下 LoRA 清空提示；`openspec validate fix-engine-default-toggle --strict`；归档；`codegraph sync`
