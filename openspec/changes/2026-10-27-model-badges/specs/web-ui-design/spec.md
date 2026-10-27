## MODIFIED Requirements

### Requirement: 侧栏「模型」导航与模型页

侧栏 MUST 在「音乐库」与用户区之间新增「模型」导航项（Phosphor `ph-hard-drives` 图标、复用 `.sb-item` 既有模式）。对应 `#view-models` 页面 MUST 承载于 `#main` 内部（不新增顶层栏、不改变三栏与底栏结构）。页面 MUST 复用既有组件模式：分段控件（`.set-seg`）、卡片、进度条，MUST NOT 引入与冻结风格冲突的新组件形态。模型清单中**每个组件行** MUST 在名称后显示且仅显示一个状态徽标：`required` 为真时显示「必备」，为假时显示「可选」；徽标 MUST 复用既有 `.mdl-req` 胶囊样式（`--text-3` 文字、`--line` 描边、11px/600），MUST NOT 新增设计令牌或改变行布局；文案 MUST 走 i18n（`models.required` / `models.optional`）。Windows 专属的 CUDA 加速套件行 MUST 同样显示「可选」。右侧的安装状态徽标（已安装 / 未安装 / 进度）不受影响。

#### Scenario: 打开模型页

WHEN 用户点击侧栏「模型」
THEN 主区显示模型清单页，创作面板隐藏、三栏与底栏不变；「模型」项呈选中态

#### Scenario: 组件状态徽标

WHEN 用户打开模型页
THEN 核心模型行名称后显示「必备」，其余每个组件行名称后显示「可选」，右侧安装状态显示不变

#### Scenario: 基线更新

WHEN 本变更实施完成
THEN `docs/ui-baseline/{en,zh}/models.png` MUST 以 1440×900 重截，其余基线图不变
