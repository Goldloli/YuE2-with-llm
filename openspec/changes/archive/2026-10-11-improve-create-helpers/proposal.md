# Proposal: improve-create-helpers

## Why

创作面板的两个辅助按钮内容单薄过时（用户确认方向：改造）：
- **✨ 歌词示例**：仅 2 条硬编码英文歌词；后端 `/api/examples` 已存在但只返回 ABC 谱示例（未含歌词），接口形同半成品；
- **🧙 风格魔法棒**：牌堆 8 组全英文、含拼写错 `trumpette`（应为 trumpet）；
- 两者均**无警告覆盖**用户已输入的内容。

## What Changes

（无视觉变更：首屏 chips 与按钮外观均不变；确认复用既有 `confirmDialog` 组件；实施后对照基线核查）

1. **`/api/examples` 扩展**：返回结构改为 `{"scores": {…原 3 个 ABC…}, "lyrics": [{"name", "lyrics", "style"}…]}`——`lyrics` 扫描 `examples/*.json` 中含歌词的条目（现有 `song.json` 英文 + `ink_moonlight.json` 中文）；attach 谱面弹窗同步适配 `scores` 子键（唯一既有消费方）。
2. **✨ 按钮接真实数据**：从「真实示例歌词（含中文）+ 2 条硬编码兜底」中随机选取；接口不可用或列表为空时回退硬编码原行为。
3. **覆盖前确认**：两个按钮在目标字段**非空**时先弹确认（「替换 / Replace」，复用 `confirmDialog`），确认后才覆盖；字段为空时直接填充（不增多余确认）。
4. **风格牌堆**：`trumpette`→`trumpet`；追加 5 组中文建议（中国风 / 国风电子 / 日系动漫 / 城市流行 / 纯音乐），并补齐词典缺失的 11 个词条（抒情慢板、唯美、国风电子、大气、日系动漫、青春、城市流行、夜晚、霓虹、阅读背景、钢琴曲）。**英文 8 组保持在牌堆前部**——首屏 chips 不变、零基线影响。
5. 非目标：不改 chips 追加行为与「换一批」；不给两个按钮加 AI 生成能力（不做 LLM 写词）；不调整牌堆顺序（中文优先排序如需另案）；不改按钮图标与布局。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `web-ui-design`: 追加辅助按钮「覆盖前确认」与「示例来源真实数据」两条交互要求（冻结基线行为修订，无视觉差异；词典增补属实施细节，不设规格需求）。

## Impact

- **代码**：`web/server.py`（examples 端点）、`web/static/app.js`（sparkle / magic wand / attach 弹窗三处）、`web/static/i18n.js`（确认文案 5 条）、`src/yue2/data/zh_style_terms.json`（+11 词条）。
- **测试**：`/api/examples` 新形状用例（scores 3 键 + lyrics 含中文条目）；词典计数仍在既有断言带内（207→218）；全量 pytest。
- **基线**：零视觉影响（首屏 chip 集不变、按钮不变）——实施后对照 create-advanced 基线确认无差异。
- **风险**：低。`/api/examples` 是内部接口，唯一消费方随本次同步适配。
