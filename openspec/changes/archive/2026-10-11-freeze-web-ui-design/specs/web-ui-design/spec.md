# Spec Delta: web-ui-design

## Purpose

将 `web/static/` 现有的暗色三栏音乐工作台视觉基线固化为设计基线契约，约束后续所有前端改动保持该风格不变，并为视觉变更建立显式声明与用户确认机制。

## ADDED Requirements

### Requirement: 设计令牌冻结

前端 MUST 以 `styles.css` `:root` 中的 CSS 自定义属性为唯一设计令牌来源，且下列令牌值 MUST NOT 被改变：`--bg: #101012`、`--bg-raise: #17171b`、`--card: #1b1b21`、`--card-soft: #1c1c1f`、`--chip: #26262d`、`--chip-hover: #30303a`、`--text: #f5f2ec`、`--text-2: #a5a5ad`、`--text-3: #6d6d76`、`--pink: #e93581`、`--danger: #f25757`、强调橙 `#e8622c`、`--radius-card: 20px`、`--radius-row: 12px`、`--font`（Inter Tight 优先）。新增样式 MUST 复用既有令牌，不得引入与之平行的硬编码色值。

#### Scenario: 新增 UI 元素用色

WHEN 任何改动新增可见 UI 元素
THEN 其颜色、圆角、字体 MUST 取自既有令牌或既有组件类，不出现新的硬编码主题色

#### Scenario: 令牌值修改

WHEN 提案要求修改上述任一令牌值
THEN 该提案 MUST 显式声明为视觉变更并经用户确认，否则不得实施

### Requirement: 布局结构冻结

页面 MUST 保持三栏 + 底栏结构：左侧 248px 固定侧边栏（`#sidebar`）、中间 450px 创作面板（`#create-panel`）、右侧弹性主区（`#main`），底部为通栏播放条（`#player`）。栏宽、层级关系、`overflow` 行为 MUST NOT 被改变。新视图 MUST 承载于 `#main` 内部，不得新增顶层栏或改变栏序。

#### Scenario: 新增主区视图

WHEN 改动新增一个主区视图（如新的列表/详情页）
THEN 它以 `#view-*` 形式挂在 `#main` 内，三栏宽度与播放条位置不变

### Requirement: 组件语言一致

新增或修改的 UI MUST 复用既有组件模式：pill 按钮（`border-radius: 999px`）、卡片（`.cp-card`，20px 圆角、`--card-soft` 底）、歌曲行（`.song-row`，84px 封面、hover 浮现操作）、模态（`#modal`，620px、20px 圆角）、右键菜单（`.ctx-item`）、toast（胶囊形、底部居中）、开关（`.switch` 橙色态）。不得引入与这些模式冲突的新组件风格（如直角卡片、亮色面板、阴影厚重的拟物控件）。

#### Scenario: 新增设置项

WHEN 改动向设置弹窗添加选项
THEN 使用 `.set-row` / `.set-seg` / `.set-input` 既有模式，视觉与相邻行一致

### Requirement: 品牌元素保留

主行动按钮（Create）MUST 保持 `aura.jpg` 渐变背景与白色加粗文字的样式；图标 MUST 使用 Phosphor（regular/fill）；logo 区保持 `YuE²` 字标。上述品牌元素 MUST NOT 被替换或移除。

#### Scenario: 新增主行动按钮

WHEN 改动新增一个主 CTA（如批量创建的确认按钮）
THEN 复用 `.create-btn` / `#create-btn` 的 aura 渐变样式，而非新设计

### Requirement: 动效克制

过渡与动画 MUST 保持克制：hover/active 过渡时长在 0.06s–0.18s 区间（既有值为 0.12s/0.15s），只允许 opacity、background、transform、border-color 类属性过渡；不得引入页面级转场动画、视差滚动或循环装饰动画（既有 `spin`/`indet`/`toast-in` 除外）。

#### Scenario: 新增 hover 反馈

WHEN 新组件需要 hover 态
THEN 过渡时长不超过 0.18s，且仅过渡背景/颜色/透明度

### Requirement: 视觉变更管控

任何改变外观、布局、组件视觉或品牌元素的提案 MUST 在 proposal 的 What Changes 中显式声明「视觉变更」及影响范围，并在用户确认后方可实施。纯文案/i18n 字符串修改、占位符更新、不可见行为修复、后端逻辑变更不属于视觉变更，无需声明。

#### Scenario: 功能改动不涉及视觉

WHEN 提案仅修改 `app.js` 的请求组装逻辑（如嗓音后缀时序），不改变任何渲染结果的结构与样式
THEN 无需视觉变更声明，但实施 MUST 不产生任何视觉差异

#### Scenario: 功能改动伴随视觉变化

WHEN 提案需要新增可见控件或调整现有控件样式
THEN proposal 显式声明「视觉变更」并列出对照的基线截图，用户确认后才实施

### Requirement: 基线截图参照

仓库 MUST 维护一套基线截图于 `docs/ui-baseline/`（固定视口 1440×900，覆盖 Create 简单/高级模式、Library、歌曲详情、设置弹窗，en 与 zh 各一套）。涉及 `web/static/` 的改动实施完成后，SHOULD 对照基线人工核查无意外视觉差异。

#### Scenario: 前端改动完成后核查

WHEN 任何触及 `web/static/` 的变更实施完毕
THEN 以相同视口截图与 `docs/ui-baseline/` 对照，确认除提案声明的视觉变更外无差异
