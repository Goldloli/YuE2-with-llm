# Spec Delta: style-prompt-localization（追加需求）

## ADDED Requirements

### Requirement: 上游原文优先（MLX 启动器）

当调用方已通过 `--style-original` 提供原始风格文本时，MLX 启动器（`tools/mlx_generate.py`）MUST 直接采信该原文并跳过二次本地化：`--style` 原样使用，`style_original` 持久化为所提供原文（二者相同时记为无原文）。仅当未提供 `--style-original` 时，MUST 按 `--style-language` 执行本地化。与 torch 管线「上游已提供 `style_original` 则跳过翻译」的语义 MUST 保持一致。

#### Scenario: 服务器下发的已翻译风格

WHEN 服务器传入英文风格（含未收录的中文残留词）与中文 `--style-original`
THEN 启动器不再对 style 二次翻译，输出目录 `request.json` 的 `style_original` 为真实中文原文

#### Scenario: 纯 CLI 使用

WHEN 直接以中文风格调用 `tools/mlx_generate.py` 且未提供 `--style-original`
THEN 按 `--style-language` 正常本地化，行为与现状一致
