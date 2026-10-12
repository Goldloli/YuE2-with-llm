# Spec Delta: style-prompt-localization（追加需求）

## ADDED Requirements

### Requirement: 原始输入展示

Web UI 在展示歌曲 style 的所有位置（歌曲流、音乐库、详情页）MUST 显示用户的原始输入（`style_original`，当该字段存在时），而不是翻译后的英文标签。翻译后的英文标签 SHOULD 以 tooltip（`title` 属性）形式提供，不得新增可见 UI 元素或改变任何样式。英文输入的歌曲（无 `style_original`）MUST 保持显示 `style` 不变。

#### Scenario: 中文输入的歌曲行

WHEN 一首歌曲带 `style_original`（中文原文）
THEN 歌曲流/音乐库/详情页的 style 文本显示中文原文，tooltip 含英文标签

#### Scenario: 英文输入的歌曲行

WHEN 一首歌曲无 `style_original`
THEN style 文本显示 `style` 字段，行为与现状一致
