# Spec Delta: web-ui-design（冻结基线的显式修订）

## ADDED Requirements

### Requirement: 侧栏「模型」导航与模型页

侧栏 MUST 在「音乐库」与用户区之间新增「模型」导航项（Phosphor `ph-hard-drives` 图标、复用 `.sb-item` 既有模式）。对应 `#view-models` 页面 MUST 承载于 `#main` 内部（不新增顶层栏、不改变三栏与底栏结构）。页面 MUST 复用既有组件模式：分段控件（`.set-seg`）、卡片、进度条，MUST NOT 引入与冻结风格冲突的新组件形态。

#### Scenario: 打开模型页

WHEN 用户点击侧栏「模型」
THEN 主区显示模型清单页，创作面板隐藏、三栏与底栏不变；「模型」项呈选中态

#### Scenario: 基线更新

WHEN 本变更实施完成
THEN `docs/ui-baseline/{en,zh}/` 全部页面因侧栏新增项重截，并新增 `models.png`（en/zh 各一张）
