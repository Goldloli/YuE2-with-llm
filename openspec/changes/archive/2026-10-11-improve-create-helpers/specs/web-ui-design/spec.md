# Spec Delta: web-ui-design（显式修订）

## ADDED Requirements

### Requirement: 辅助按钮覆盖前确认

创作面板的歌词示例按钮（✨）与风格魔法棒按钮在目标输入框**非空**时，MUST 先经确认对话框（复用既有 `confirmDialog` 组件）取得用户确认后才覆盖内容；输入框为空时 MUST 直接填充。确认文案 MUST 两语（en/zh）齐备。

#### Scenario: 非空字段被覆盖

WHEN 用户已在歌词框输入内容后点击 ✨
THEN 弹出「替换歌词？」确认；取消则内容不变，确认则以示例歌词替换

#### Scenario: 空字段直接填充

WHEN 歌词框为空时点击 ✨
THEN 直接填入示例歌词，不弹确认

### Requirement: 示例内容来源真实数据

歌词示例按钮 MUST 优先从后端示例数据（`/api/examples` 的 `lyrics` 列表，含中文条目）中随机选取；后端不可用或列表为空时 MUST 回退到内置兜底示例。风格魔法棒的每组建议 MUST 通过内置词典可翻译（中文组不得含未收录词条）。

#### Scenario: 中文示例可达

WHEN 后端示例可用且用户点击 ✨
THEN 存在选中中文示例歌词的可能（示例池含中文条目）

#### Scenario: 中文建议组可翻译

WHEN 用户点选任一中文建议 chips 或整组填入风格框
THEN 生成时全部词条可经词典翻译为英文标签，无未收录残留
