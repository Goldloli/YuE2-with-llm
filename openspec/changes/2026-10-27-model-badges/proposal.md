# Proposal: 2026-10-27-model-badges

## Why

模型页现在只有「核心模型」一行带 `必备` 徽标；解码器、扩展工具、LoRA、音频转录、MLX 变体、Windows CUDA 套件等行都没有任何状态标注，用户无法一眼看出哪些是必须下载、哪些是可选的。用户要求：**所有模型行都标出「必备」或「可选」**，与第一行（核心模型）风格一致。

## What Changes

- **视觉变更（已由用户明确要求）**：模型页每个组件行在名称后统一显示状态徽标——
  - `required: true` → `必备`（沿用现有 `.mdl-req` 胶囊样式）
  - `required: false` → `可选`（同一 `.mdl-req` 样式，不新增设计令牌、不改布局/字号/颜色）
  - 覆盖范围：核心模型、解码器、扩展工具、LoRA 风格、音频转录、MLX 变体（macOS），以及 Windows 专属的 CUDA 加速套件行。
- **i18n**：新增 `models.optional`（zh「可选」/ en「optional」），复用现有 `models.required`。
- **基线**：按前端冻结规范重截 `docs/ui-baseline/{en,zh}/models.png`（1440×900），体现新版徽标；其余基线图不变。
- **规格**：MODIFIED `web-ui-design` 的「侧栏『模型』导航与模型页」要求，补充「每行 MUST 标注必备/可选」。
- **发布**：该改动会进入前端静态资源，需要重建一键包：push main 更新滚动包；打 `v0.1.10` 发布双平台正式包。

## Capabilities

### Modified Capabilities

- `web-ui-design`：模型页组件行新增必备/可选状态徽标（视觉变更，用户已确认）。

## Impact

- 修改：`web/static/app.js`（`modelRowHtml`、`cudaKitRowHtml`）、`web/static/i18n.js`（新增 `models.optional`）、`docs/ui-baseline/{en,zh}/models.png`。
- 新增：无（复用既有 `.mdl-req` 样式）。
- 兼容性：纯前端文案/徽标变更，不影响接口、模型下载、CUDA 套件逻辑；`required` 字段服务端已有。
