# Spec Delta: web-ui-design（修订）

## ADDED Requirements

### Requirement: 侧栏「LLM 配置」导航与配置页

侧栏 MUST 在「模型」之后新增「LLM 配置」导航项（Phosphor `ph-robot` 图标、复用 `.sb-item` 既有模式）。对应 `#view-llm` 页面 MUST 承载于 `#main` 内部（不新增顶层栏、不改变三栏与底栏结构），并复用既有组件模式：`.set-input` 输入行、`.set-seg` 分段控件、pill 按钮、`.set-note` 说明。页面 MUST 提供：base_url、model、api_key（仅掩码占位、不回显明文）、超时（1–60 秒）、增强输出语言（中文词表 / English tags 两档分段控件）、「测试连接」「保存」；保存与测试结果 MUST 以既有 toast 反馈。MUST NOT 引入与冻结风格冲突的新组件形态。

#### Scenario: 打开配置页

WHEN 用户点击侧栏「LLM 配置」
THEN 主区显示配置页，创作面板隐藏、三栏与底栏不变；「LLM 配置」项呈选中态

#### Scenario: 基线更新

WHEN 本变更实施完成
THEN `docs/ui-baseline/{en,zh}/` 全部页面因侧栏新增项重截，并新增 `llm.png`（en/zh 各一张）

### Requirement: 魔法棒 LLM 增强交互

已配置 LLM 时，风格魔法棒按钮 MUST 执行 LLM 增强：读取当前风格文本发起 `POST /api/llm/enhance`；请求期间按钮 MUST 呈加载/禁用态并 MUST 防止重复点击；成功后 MUST 以既有 `confirmDialog` 展示增强结果——确认后以结果替换风格框内容并触发其 `input` 事件（依赖其的表单状态同步刷新），取消则保留原文；失败 MUST 保留原文并 toast 显示可读错误；风格框为空时 MUST 提示先输入风格描述且 MUST NOT 发起请求。未配置 LLM 时魔法棒 MUST 保持既有牌堆行为不变。交互文案 MUST 两语（en/zh）齐备。

#### Scenario: 增强并应用

WHEN 风格框含「黑人说唱」且已配置 LLM，点击魔法棒
THEN 弹出含增强结果的确认；确认后风格框内容为增强结果，创作按钮状态同步刷新

#### Scenario: 取消保留原文

WHEN 增强结果弹出后用户取消
THEN 风格框内容保持原样

#### Scenario: 失败保持原文

WHEN 增强请求失败
THEN 风格框内容不变，toast 显示可读错误

#### Scenario: 空输入

WHEN 风格框为空时点击魔法棒（已配置 LLM）
THEN 提示先输入风格描述，不发起请求

#### Scenario: 未配置保持牌堆

WHEN 未配置 LLM 时点击魔法棒
THEN 行为与现状一致（非空确认后覆盖、空则直接填入下一组示例牌堆）

## MODIFIED Requirements

### Requirement: 辅助按钮覆盖前确认

创作面板的歌词示例按钮（✨）MUST 在目标输入框非空时先经确认对话框（复用既有 `confirmDialog` 组件）取得用户确认后才覆盖内容；输入框为空时 MUST 直接填充。风格魔法棒按钮：牌堆模式（未配置 LLM）下 MUST 遵守同样的「非空先确认、空则直接填充」；LLM 增强模式下 MUST 以「增强结果预览确认」实现覆盖前确认（见「魔法棒 LLM 增强交互」），风格框为空时 MUST 提示而非填充。各确认文案 MUST 两语（en/zh）齐备。

#### Scenario: 非空字段被覆盖

WHEN 用户已在歌词框输入内容后点击 ✨
THEN 弹出「替换歌词？」确认；取消则内容不变，确认则以示例歌词替换

#### Scenario: 空字段直接填充

WHEN 歌词框为空时点击 ✨，或未配置 LLM 时风格框为空点击魔法棒
THEN 直接填入示例歌词 / 示例牌堆，不弹确认
