# Spec Delta: web-ui-design（冻结基线的显式修订）

## ADDED Requirements

### Requirement: 设置弹窗分组布局

设置弹窗 MUST 由分组构成（创作默认 / 生成行为 / 模型与性能 / 界面 / 高级与维护 / 状态），分组以 12px 小标题（13px、`--text-3`、字重 600）与 `--line-soft` 细分隔呈现；分组内各行 MUST 沿用既有 `.set-row` / `.set-seg` / `.set-input` / `.set-note` 组件，MUST NOT 引入新的行控件形态。弹窗 MUST 维持现有宽度、圆角与内部滚动行为。

#### Scenario: 分组标题

WHEN 打开设置弹窗
THEN 各设置项按组归位，组标题与小分隔线可见，行视觉与旧版逐行一致

#### Scenario: CUDA 专属项隐藏

WHEN 在非 CUDA 设备上打开设置
THEN FP8 量化与 AR 卸载行不显示，其余分组布局不受影响
