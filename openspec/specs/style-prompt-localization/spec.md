# style-prompt-localization Specification

## Purpose
在请求构建前对 style/tags 提示词做语言检测与中文→英文标签翻译，使中文用户可以用自然语言描述风格，同时保持模型输入协议（英文 `[Tags]`）与运行结果的可复现性不变。

## Requirements

### Requirement: 中文 style 检测

系统 SHALL 在组装模型输入模板之前，检测 style/tags 文本是否包含中日韩统一表意文字（CJK）。纯英文（含数字、标点、现有英文标签）的 style MUST 被判定为无需翻译。

#### Scenario: 纯中文 style

WHEN 用户提交 style「雷鬼，小调合唱，木管，流行电子」且模式为 `auto`
THEN 系统判定其包含中文，进入翻译流程

#### Scenario: 纯英文 style

WHEN 用户提交 style「reggae, minor choir, woodwinds, electro pop」且模式为 `auto`
THEN 系统判定其不含中文，style 原样通过，不发生任何提供者调用

#### Scenario: 中英混合 style

WHEN 用户提交 style「Mandarin, 温暖钢琴, acoustic pop」且模式为 `auto`
THEN 系统判定其包含中文进入翻译流程，且翻译输出 MUST 保留原有英文标签的语义

### Requirement: 翻译后进入模板

判定为中文的 style SHALL 被翻译为英文逗号分隔标签，且进入 `SongRequest.text()` 的 `[Tags]` 块的 MUST 是翻译后的英文文本。歌词（lyrics）MUST 保持原样，不做任何语言检测或翻译。

#### Scenario: 模板内容纯净

WHEN 中文 style 完成翻译
THEN 最终 `[Tags]` 块内容为英文标签，模型输入模板结构与英文输入时完全一致

#### Scenario: 歌词不受影响

WHEN 用户提交中文 style 与中文歌词
THEN 仅 style 被翻译，歌词逐字保留在 `[Lyrics]` 块中

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

### Requirement: 持久化与可复现

翻译 SHALL 发生在请求身份哈希计算之前。持久化的 `request.json` MUST 同时包含翻译后的 `style`（英文，参与哈希与生成）与 `style_original`（用户原始输入）。再次运行同一请求 MUST 产生与首次一致的身份与输出路径。

#### Scenario: 持久化字段

WHEN 中文 style 请求被持久化
THEN `request.json` 中 `style` 为英文标签、`style_original` 为中文原文

#### Scenario: 复现一致

WHEN 使用同一 `request.json` 重新运行
THEN 不再触发翻译，身份哈希与首次运行一致

### Requirement: 配置开关

系统 SHALL 提供 `auto | en | off` 三档 style 语言模式（CLI flag 与 Web 设置），默认 `auto`。`en` 或 `off` 时 MUST 完全跳过检测与翻译，行为与当前版本一致。

#### Scenario: 显式关闭

WHEN 用户设置 `--style-language off` 并提交中文 style
THEN style 原样透传，且不产生翻译告警之外的任何行为变化

### Requirement: Web 嗓音后缀时序

Web UI 的嗓音按钮（male/female vocals）追加的英文后缀 MUST 作用于翻译完成后的英文 style，不得拼接到未翻译的中文文本上。

#### Scenario: 中文 style + 嗓音按钮

WHEN 用户在 Web UI 输入中文 style 并选择「女声」
THEN 追加 `female vocals` 发生在翻译之后，最终 `[Tags]` 块为纯英文

### Requirement: 原始输入展示

Web UI 在展示歌曲 style 的所有位置（歌曲流、音乐库、详情页）MUST 显示用户的原始输入（`style_original`，当该字段存在时），而不是翻译后的英文标签。翻译后的英文标签 SHOULD 以 tooltip（`title` 属性）形式提供，不得新增可见 UI 元素或改变任何样式。英文输入的歌曲（无 `style_original`）MUST 保持显示 `style` 不变。

#### Scenario: 中文输入的歌曲行

WHEN 一首歌曲带 `style_original`（中文原文）
THEN 歌曲流/音乐库/详情页的 style 文本显示中文原文，tooltip 含英文标签

#### Scenario: 英文输入的歌曲行

WHEN 一首歌曲无 `style_original`
THEN style 文本显示 `style` 字段，行为与现状一致

### Requirement: 上游原文优先（MLX 启动器）

当调用方已通过 `--style-original` 提供原始风格文本时，MLX 启动器（`tools/mlx_generate.py`）MUST 直接采信该原文并跳过二次本地化：`--style` 原样使用，`style_original` 持久化为所提供原文（二者相同时记为无原文）。仅当未提供 `--style-original` 时，MUST 按 `--style-language` 执行本地化。与 torch 管线「上游已提供 `style_original` 则跳过翻译」的语义 MUST 保持一致。

#### Scenario: 服务器下发的已翻译风格

WHEN 服务器传入英文风格（含未收录的中文残留词）与中文 `--style-original`
THEN 启动器不再对 style 二次翻译，输出目录 `request.json` 的 `style_original` 为真实中文原文

#### Scenario: 纯 CLI 使用

WHEN 直接以中文风格调用 `tools/mlx_generate.py` 且未提供 `--style-original`
THEN 按 `--style-language` 正常本地化，行为与现状一致

### Requirement: 词典覆盖与维护

内置中文词典 MUST 覆盖常用中文音乐术语，类别包括：乐器（民族与西洋）、流派、情绪、人声、速度/节拍/调性、制作与年代、国风意境、演唱语言。总词条数 MUST ≥ 290；演唱语言 MUST 覆盖不少于 15 种（中文、粤语、闽南/台语、英语、日语、韩语、法语、西班牙语、俄语、德语、意大利语、葡萄牙语、阿拉伯语、泰语、越南语）。映射值 MUST 为不含中文的英文标签。已知不理想映射 MUST 修正：「慢板」MUST 译为 `adagio`（`抒情慢板` 保持 `slow ballad`）、「阅读背景」MUST 译为 `background music`。新增词条 MUST NOT 改变任何既有词条（除修正清单外）的翻译结果；最长匹配语义 MUST 保持——前缀重叠的新词 MUST NOT 拆坏既有长词（如「回响贝斯」仍译为 `dubstep`，不受新增「回响」影响）。

#### Scenario: 新增词条命中

WHEN style 为「洞箫，笙，埙，大号，木琴」
THEN 翻译输出为「xiao, sheng, xun, tuba, xylophone」

#### Scenario: 修正后的映射

WHEN style 为「慢板」「阅读背景」「抒情慢板」
THEN 分别译为「adagio」「background music」「slow ballad」

#### Scenario: 最长匹配不受新词影响

WHEN style 为「回响贝斯，回响」
THEN 译为「dubstep, dub」，MUST NOT 拆成「dub」与残留

#### Scenario: 演唱语言覆盖

WHEN style 为「俄语，德语，意大利语，广东话」
THEN 译为「Russian, German, Italian, Cantonese」

#### Scenario: 词表结构校验

WHEN 测试读取内置词表
THEN 全部键含中文、全部值为非空纯英文、总条数 ≥ 290

### Requirement: 词表导出文档

仓库 MUST 提供生成脚本 `tools/export_style_terms.py`，从 `src/yue2/data/zh_style_terms.json` 生成中文风格词表文档 `docs/style-terms.md`。该文档 MUST 为生成物（含「请勿手改」标注与再生成命令）、MUST NOT 手工编辑；内容 MUST 按类别分组渲染为中英对照 Markdown 表格，并附词条统计（总条数与英文去重数）与同义词汇总。词表中每个词条 MUST 归属且仅归属一个类别；新增词条若未在脚本类别表中归类，MUST 归入「其他」并在生成输出中列出提示。脚本 MUST 提供 `--check` 模式：与仓库内文档一致时以 0 退出，不一致时以非零退出并提示重新生成。

#### Scenario: 文档与源数据一致

WHEN 运行 `python tools/export_style_terms.py --check`
THEN 仓库内 `docs/style-terms.md` 与源词表渲染结果逐字一致时校验通过（退出码 0）

#### Scenario: 词表更新后同步

WHEN 向 `zh_style_terms.json` 新增或修改词条后重新运行生成脚本
THEN 文档 MUST 反映全部变更；此前未归类的词条出现在「其他」分组且在生成输出中被列出

#### Scenario: 类别全覆盖

WHEN 测试校验词典与类别表的对应关系
THEN 词典中不存在未归类词条（脚本类别表覆盖全部词条），同义合并展示与同义词汇总 MUST 与词典内容自动对应

#### Scenario: 分组渲染

WHEN 生成文档
THEN 词条按类别分组渲染为表格；同一类别内多个中文词指向同一英文标签时 SHOULD 合并为一行展示；跨类别的同义词组 MUST 出现在同义词汇总中
