# Spec Delta: style-prompt-localization（新增）

## ADDED Requirements

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
