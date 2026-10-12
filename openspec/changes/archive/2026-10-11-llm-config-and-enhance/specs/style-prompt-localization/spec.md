# Spec Delta: style-prompt-localization（修订）

## MODIFIED Requirements

### Requirement: 可插拔翻译提供者链

系统 SHALL 按以下混合策略完成中文 style 翻译：(1) 先执行内置词典——若词典输出**不再含中文残留**（全覆盖）MUST 直接采用，且 MUST NOT 发起 LLM 调用；(2) 词典未全覆盖且配置了 LLM 端点（设置优先于环境变量）时 MUST 使用 LLM 完成整段翻译；(3) LLM 未配置或调用失败时 MUST 采用词典的部分结果（未覆盖片段原样保留）。任一提供者失败 MUST 自动降级到下一可用手段，不得中断生成。

#### Scenario: 词典全覆盖跳过 LLM

WHEN style 为「雷鬼，木管，慵懒，慢速」且已配置 LLM 端点
THEN 输出 `reggae, woodwinds, laid-back, slow tempo`，且 MUST NOT 发生 LLM 调用

#### Scenario: LLM 端点可用

WHEN style 为「黑人说唱」（词典未全覆盖）且已配置 LLM 端点
THEN 使用 LLM 完成整段翻译，输出完整英文标签

#### Scenario: 回退到内置词典

WHEN 词典未全覆盖且未配置 LLM 端点、或 LLM 端点调用失败
THEN 采用内置词典的部分结果（未覆盖片段原样保留）并记录告警，生成流程不中断

#### Scenario: 全部不可用

WHEN 无任何提供者可用
THEN style 原样透传并在日志/Web UI 输出「未翻译」告警，生成流程不中断
