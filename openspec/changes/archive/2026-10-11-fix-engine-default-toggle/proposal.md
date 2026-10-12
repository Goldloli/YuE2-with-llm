# Proposal: fix-engine-default-toggle

## Why

用户报告：模型页「默认推理引擎」无法点击。复现确认（浏览器实测）：点击「PyTorch」后**服务器实际已保存** `default_backend=torch`，但界面无任何变化；反复点击仍无反馈，表现为控件失效。

根因（三处联动缺陷，均由 model-manager 引入）：
1. 活动态渲染绑定 `state.backend`（**会话**当前引擎）而非 `s.default_backend`（本控件语义值）——保存默认值后显示不动；
2. 轮询「无变化跳过重建」的 sig 未包含 `default_backend`——保存后判定"无变化"，跳过重建；
3. 点击处理器只保存默认值，不同步会话（pill/引擎展示不随动，进一步放大"没反应"观感）。

## What Changes

（行为修复，无视觉变化，无基线影响）

1. **活动态修正**：模型页「默认推理引擎」的活动态渲染改用 `s.default_backend`（与控件标签「默认」语义一致）；
2. **跳过重建的 sig 修正**：将 `state.backend` 替换为 `s.default_backend`（页面展示的实际数据源）；
3. **点击即时生效**：保存 `default_backend` 后同步会话引擎（调用既有 `setBackend`：刷新 pill、切 MLX 时清空 LoRA 并提示）——`default_backend` 不在 app-settings「仅作用于初始状态」清单内（该清单为 mode/max_seconds/cfg/sort/start_view），同步会话不违反既有规格；
4. **一致性**：设置弹窗中的同名字段（默认推理引擎）点击后同样同步会话（一行改动），两个入口行为一致；
5. 非目标：不改 MLX 变体/默认 LoRA/下载源三个控件的既有行为（经复测均正常）；不改引擎切换的校验与回退逻辑。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `model-management`: 追加「默认模型设置控件即时反馈」行为要求（模型页与设置页的默认引擎切换 MUST 即时反映到界面与会话）。

## Impact

- **代码**：`web/static/app.js`（模型页引擎 seg 渲染/处理器/sig 三处、设置页通用 seg 处理器一处）。
- **测试**：浏览器回归——两页点按引擎即时生效（活动态迁移 + pill 同步 + 持久化），切 MLX 时 LoRA 清空提示正常。
- **风险**：极低；仅触及引擎默认值的展示与同步路径。
