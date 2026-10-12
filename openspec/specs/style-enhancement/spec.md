# style-enhancement Specification

## Purpose
TBD - created by archiving change llm-config-and-enhance. Update Purpose after archive.

## Requirements

### Requirement: LLM 风格增强端点

`POST /api/llm/enhance` MUST 接受 `{style}` 并返回理解后的风格标签串。端点 MUST 将内置词表（`src/yue2/data/zh_style_terms.json`）注入提示词，要求模型把用户的自由描述理解为由词表词汇构成的风格标签（可合理补全风格要素）；输出语言由 `llm_enhance_output` 控制：`zh` MUST 以词表中文词汇为主（词表无可对应时 MAY 保留少量英文补充），`en` MUST 为英文标签。返回值 MUST 经服务端清洗：去除引号、反引号、代码围栏、换行与解释性文字，按逗号分词，去空段、去重，长度 MUST ≤200 字符且词条数 MUST ≤12。空 `style` MUST 返回 422。未配置 LLM 时 MUST 返回 4xx 明确错误且 MUST NOT 发起任何外部调用。失败（超时/连接失败/HTTP 错误/空输出）MUST 返回可读错误且 MUST NOT 修改任何持久化状态。该端点 MUST NOT 触碰生成路径。

#### Scenario: 理解并转化

WHEN `style=黑人说唱`、输出模式 `zh`
THEN 返回逗号分隔标签串，主体为词表词汇（说唱、嘻哈、男声、重拍 一类的组合形态）

#### Scenario: 输出清洗

WHEN 模型返回带引号、代码围栏、换行或前后解释文字的结果
THEN 返回值为单行、逗号分隔、已去重且不超限的标签串

#### Scenario: 未配置拒绝

WHEN 未配置任何 LLM 端点（设置与环境变量均无）时调用
THEN 返回 4xx 明确错误，且不发起外部请求

#### Scenario: 失败不破坏状态

WHEN LLM 超时或返回错误
THEN 响应为可读错误，服务端 MUST NOT 写入任何配置或歌曲数据

#### Scenario: 输出模式

WHEN 同一输入分别在 `zh` 与 `en` 模式下增强
THEN 前者以中文词表词汇为主，后者为英文标签
