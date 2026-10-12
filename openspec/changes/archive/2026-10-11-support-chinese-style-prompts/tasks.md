# Tasks: support-chinese-style-prompts

## 1. 核心模块

- [x] 1.1 新建 `src/yue2/style_localization.py`：CJK 检测（Unicode 区间）、`localize_style(style, mode, provider_chain)` 返回 `(final_style, style_original, translated)`；验证：`pytest tests/test_style_localization.py` 中新检测用例通过
- [x] 1.2 实现内置词典提供者：术语数据文件 + 切片翻译/未命中保留原文；验证：词典用例（流派/乐器/情绪/嗓音/速度各至少一条）通过
- [x] 1.3 实现 LLM 端点提供者（OpenAI 兼容，env 配置 base_url/api_key/model，超时 ≤10s 自动降级）；验证：mock 端点成功/超时/错误三类用例通过
- [x] 1.4 实现提供者链编排与透传告警；验证：链顺序与降级路径用例通过

## 2. 入口接入

- [x] 2.1 CLI：`request_kwargs` 前接入 `localize_style`，新增 `--style-language auto|en|off`（默认 auto）；验证：`yue2 generate --help` 可见新 flag，`tests/test_cli_public.py` 扩展用例通过
- [x] 2.2 Pipeline：`pipeline.__call__` 在身份哈希前应用翻译，`request.json` 持久化 `style` + `style_original`；验证：持久化字段与哈希幂等用例通过
- [x] 2.3 Web：`queue_from_request` 接入翻译，嗓音后缀从 `app.js` 前端拼接改为后端按 `vocal_gender` 在翻译后追加；响应含 `style_warning`；验证：中文 style + 女声按钮的请求最终 `[Tags]` 为纯英文
- [x] 2.4 MLX：`tools/mlx_generate.py` 同样接入；验证：MLX 路径请求构建用例通过

## 3. 测试与回归

- [x] 3.1 新增 `tests/test_style_localization.py`（检测、翻译、链降级、持久化、开关 off 透传）；验证：文件内全部用例通过
- [x] 3.2 对齐 `tests/test_protocol.py` 风格，固定中文输入最终 `[Tags]` 块内容；验证：模板纯净性用例通过
- [x] 3.3 全量回归：`pytest` 全绿，且既有英文 fixture 行为零变化

## 4. 文档与收尾

- [x] 4.1 更新 `AGENTS.md`「提示词现状」、`skills/yue2-music/SKILL.md`、`docs/generation.md` 的中文 style 说明；验证：文档与实现一致
- [x] 4.2 `openspec validate support-chinese-style-prompts` 通过，准备归档
