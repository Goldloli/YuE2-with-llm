# Proposal: expand-style-terms

## Why

内置中文词典（`src/yue2/data/zh_style_terms.json`）自 `support-chinese-style-prompts` 落地以来共 218 条。全量审阅（逐条导出核对）发现两类问题：

1. **两处映射不理想**：「慢板」→`slow ballad` 把纯速度记号译成了曲风（与同组的 中板→moderato、快板→allegro 不一致）；「阅读背景」→`reading background` 英文不地道；
2. **常用词缺口**：民族/西洋乐器、现代流派、情绪、制作与年代、国风意境、演唱语言六类均有常见中文词未收录——用户用这些词时会被「最长匹配」跳过、原样残留进 `[Tags]`，模型无法理解。

用户确认：修 2 处翻译 + 补 60~80 条。

## What Changes

（纯数据与测试变更，无视觉变化、无运行时逻辑变化）

1. **修正 2 处映射**：「慢板」→ `adagio`（「抒情慢板」保持 `slow ballad` 不变）；「阅读背景」→ `background music`；
2. **新增 80 条词条（218 → 298）**，六组：

   - **乐器 +19**：箫→xiao、洞箫→xiao、笙→sheng、阮→ruan、三弦→sanxian、柳琴→liuqin、马头琴→morin khuur、埙→xun、陶笛→ocarina、锣→gong、尺八→shakuhachi、大号→tuba、木琴→xylophone、马林巴→marimba、钟琴→glockenspiel、竖笛→recorder、铃鼓→tambourine、定音鼓→timpani、手鼓→hand drums
   - **流派 +22**：交响乐→symphony、管弦乐→orchestral、科技舞曲→techno、迷幻→psychedelic、迷幻摇滚→psychedelic rock、硬摇滚→hard rock、硬核→hardcore、碎拍→breakbeat、融合爵士→jazz fusion、蓝草→bluegrass、回响→dub、未来贝斯→future bass、电音→electronic、弗拉门戈→flamenco、探戈→tango、华尔兹→waltz、进行曲→march、室内乐→chamber music、后朋克→post-punk、新古典→neoclassical、京剧→Peking opera、巴洛克→baroque
   - **情绪 +13**：伤感→sentimental、兴奋→excited、澎湃→powerful、惆怅→wistful、惬意→cozy、神圣→sacred、诡异→eerie、幽默→humorous、轻松→lighthearted、失恋→heartbroken、优雅→elegant、阳光→sunny、忧伤→melancholy
   - **制作/年代/编制 +10**：混响→reverb、失真→distortion、空间感→spacious、极简→minimal、80年代→80s、90年代→90s、黑胶→vinyl、独奏→solo、合奏→ensemble、清唱→a cappella
   - **国风意境 +7**：禅意→zen、水墨→ink painting、江湖→wuxia、武侠→wuxia、仙侠→xianxia、敦煌→Dunhuang、国潮→modern Chinese style
   - **演唱语言 +9**：俄语→Russian、德语→German、意大利语→Italian、葡萄牙语→Portuguese、阿拉伯语→Arabic、泰语→Thai、越南语→Vietnamese、广东话→Cantonese、闽南语→Hokkien（语言类合计 15 种）

3. **词表文件按 Unicode 排序插入**（保持既有排序，既有行不动，diff 仅新增）；
4. **测试同步**：`tests/test_style_localization.py` 的「慢板」样例值更新为 `adagio`；词表规模断言 `150–250` 调整为 `250–350`；新增回归样例——新增词命中、最长匹配不受影响（「回响贝斯」仍为 `dubstep`、「洞箫」仍为 `xiao`）、修正后的映射；
5. **生成物衔接**：词表文档 `docs/style-terms.md`（`style-terms-glossary` 提案，实施时自动包含新词条）——建议先本变更、后生成文档。

非目标（Non-goals）：不改匹配算法与提供者链；不做「部分命中残留」告警（另一议题）；不删既有词条；不改 Web UI 与示例牌堆。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `style-prompt-localization`: 新增「词典覆盖与维护」要求——覆盖类别（乐器/流派/情绪/人声/速度/制作/国风/语言）、规模 ≥ 290、演唱语言 ≥ 15 种、修正清单（慢板/阅读背景/抒情慢板）、扩充不得改变既有词条结果。

## Impact

- **数据**：`src/yue2/data/zh_style_terms.json`（+80 条、2 处值修正，218→298）。
- **测试**：`tests/test_style_localization.py`（慢板样例、规模断言、新增回归样例）。
- **文档**：`docs/style-terms.md` 待 `style-terms-glossary` 确认后生成/重生成，届时自动反映本变更。
- **风险**：低——纯数据与测试；最长匹配语义已确认可保护「回响贝斯」等前缀重叠词；所有新增值为纯 ASCII 英文（满足既有测试约束）。
