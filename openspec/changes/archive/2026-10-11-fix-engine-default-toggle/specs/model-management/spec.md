# Spec Delta: model-management（追加需求）

## ADDED Requirements

### Requirement: 默认模型设置控件即时反馈

模型页「默认设置」卡中的控件（默认推理引擎、默认 MLX 变体、默认 LoRA）MUST 在点击后即时反映到界面：活动态 MUST 渲染自所保存的设置值（而非会话瞬时状态），任何轮询跳过重建的判定 MUST 将该值纳入变化检测。默认推理引擎的切换 MUST 同步当前会话引擎（创作面板 pill 随动；切至 MLX 且已选 LoRA 时按既有规则清空并提示）。设置弹窗中的同名字段 MUST 具有相同行为。

#### Scenario: 模型页切换默认引擎

WHEN 用户在模型页把默认引擎从 MLX 切到 PyTorch
THEN 活动态立即迁移到 PyTorch、创作面板 pill 同步为 PyTorch、刷新页面后设置保持

#### Scenario: 无反馈不得发生

WHEN 用户点击任一默认设置控件
THEN 界面 MUST 产生与服务器状态一致的可见变化（活动态迁移或既有提示），不得出现「点击无反应」
