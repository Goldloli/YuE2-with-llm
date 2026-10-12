# web-ui-design Specification

## Purpose
将 `web/static/` 现有的 Suno 像素级复刻风格固化为设计基线契约，约束后续所有前端改动保持该风格不变，并为视觉变更建立显式声明与用户确认机制。

## Requirements

### Requirement: 设计令牌冻结

前端 MUST 以 `styles.css` `:root` 中的 CSS 自定义属性为唯一设计令牌来源，且下列令牌值 MUST NOT 被改变：`--bg: #101012`、`--bg-raise: #17171b`、`--card: #1b1b21`、`--card-soft: #1c1c1f`、`--chip: #26262d`、`--chip-hover: #30303a`、`--text: #f5f2ec`、`--text-2: #a5a5ad`、`--text-3: #6d6d76`、`--pink: #e93581`、`--danger: #f25757`、强调橙 `#e8622c`、`--radius-card: 20px`、`--radius-row: 12px`、`--font`（Inter Tight 优先）。新增样式 MUST 复用既有令牌，不得引入与之平行的硬编码色值。

#### Scenario: 新增 UI 元素用色

WHEN 任何改动新增可见 UI 元素
THEN 其颜色、圆角、字体 MUST 取自既有令牌或既有组件类，不出现新的硬编码主题色

#### Scenario: 令牌值修改

WHEN 提案要求修改上述任一令牌值
THEN 该提案 MUST 显式声明为视觉变更并经用户确认，否则不得实施

### Requirement: 布局结构冻结

页面 MUST 保持三栏 + 底栏结构：左侧 248px 固定侧边栏（`#sidebar`）、中间 450px 创作面板（`#create-panel`）、右侧弹性主区（`#main`），底部为通栏播放条（`#player`）。栏宽、层级关系、`overflow` 行为 MUST NOT 被改变。新视图 MUST 承载于 `#main` 内部，不得新增顶层栏或改变栏序。

#### Scenario: 新增主区视图

WHEN 改动新增一个主区视图（如新的列表/详情页）
THEN 它以 `#view-*` 形式挂在 `#main` 内，三栏宽度与播放条位置不变

### Requirement: 组件语言一致

新增或修改的 UI MUST 复用既有组件模式：pill 按钮（`border-radius: 999px`）、卡片（`.cp-card`，20px 圆角、`--card-soft` 底）、歌曲行（`.song-row`，84px 封面、hover 浮现操作）、模态（`#modal`，620px、20px 圆角）、右键菜单（`.ctx-item`）、toast（胶囊形、底部居中）、开关（`.switch` 橙色态）。不得引入与这些模式冲突的新组件风格（如直角卡片、亮色面板、阴影厚重的拟物控件）。

#### Scenario: 新增设置项

WHEN 改动向设置弹窗添加选项
THEN 使用 `.set-row` / `.set-seg` / `.set-input` 既有模式，视觉与相邻行一致

### Requirement: 品牌元素保留

主行动按钮（Create）MUST 保持 `aura.jpg` 渐变背景与白色加粗文字的样式；图标 MUST 使用 Phosphor（regular/fill）；logo 区保持 `YuE²` 字标。上述品牌元素 MUST NOT 被替换或移除。

#### Scenario: 新增主行动按钮

WHEN 改动新增一个主 CTA（如批量创建的确认按钮）
THEN 复用 `.create-btn` / `#create-btn` 的 aura 渐变样式，而非新设计

### Requirement: 动效克制

过渡与动画 MUST 保持克制：hover/active 过渡时长在 0.06s–0.18s 区间（既有值为 0.12s/0.15s），只允许 opacity、background、transform、border-color 类属性过渡；不得引入页面级转场动画、视差滚动或循环装饰动画（既有 `spin`/`indet`/`toast-in` 除外）。

#### Scenario: 新增 hover 反馈

WHEN 新组件需要 hover 态
THEN 过渡时长不超过 0.18s，且仅过渡背景/颜色/透明度

### Requirement: 视觉变更管控

任何改变外观、布局、组件视觉或品牌元素的提案 MUST 在 proposal 的 What Changes 中显式声明「视觉变更」及影响范围，并在用户确认后方可实施。纯文案/i18n 字符串修改、占位符更新、不可见行为修复、后端逻辑变更不属于视觉变更，无需声明。

#### Scenario: 功能改动不涉及视觉

WHEN 提案仅修改 `app.js` 的请求组装逻辑（如嗓音后缀时序），不改变任何渲染结果的结构与样式
THEN 无需视觉变更声明，但实施 MUST 不产生任何视觉差异

#### Scenario: 功能改动伴随视觉变化

WHEN 提案需要新增可见控件或调整现有控件样式
THEN proposal 显式声明「视觉变更」并列出对照的基线截图，用户确认后才实施

### Requirement: 基线截图参照

仓库 MUST 维护一套基线截图于 `docs/ui-baseline/`（固定视口 1440×900，覆盖 Create 简单/高级模式、Library、歌曲详情、设置弹窗，en 与 zh 各一套）。涉及 `web/static/` 的改动实施完成后，SHOULD 对照基线人工核查无意外视觉差异。

#### Scenario: 前端改动完成后核查

WHEN 任何触及 `web/static/` 的变更实施完毕
THEN 以相同视口截图与 `docs/ui-baseline/` 对照，确认除提案声明的视觉变更外无差异

### Requirement: 创作面板卡片缝隙

创作面板的模式容器（`#pane-simple`、`#pane-advanced`）MUST 以 flex 纵列布局分隔各 `.cp-card`，卡片间距 MUST 为 16px。卡片自身的圆角、底色、内边距 MUST NOT 改变。

#### Scenario: 高级模式卡片分隔

WHEN 创作面板处于高级模式
THEN 歌词、风格、更多选项等相邻卡片之间有 16px 可见缝隙，卡片样式与令牌不变

### Requirement: 风格卡清空按钮

高级模式的风格卡头部 MUST 提供清空按钮（复用 `.cp-tool` 模式与 Phosphor trash 图标），点击 MUST 清空风格输入框并触发其 `input` 事件。按钮视觉 MUST 与「更多选项」卡的重置按钮一致。

#### Scenario: 一键清空风格

WHEN 风格输入框非空且用户点击清空按钮
THEN 输入框清空，依赖其内容的表单状态（如创作按钮禁用态）同步刷新

### Requirement: 时长控制一级入口

「更多选项」MUST 直接包含「长度上限（秒）」字段（number input，5–360，留空为自动），映射到既有 `max_seconds` 请求参数；「高级采样」二级折叠内 MUST NOT 再出现同义字段。字段的视觉 MUST 复用 `.cp-field` 既有模式。

#### Scenario: 设置时长并提交

WHEN 用户在「更多选项」填入 20 并创作
THEN 请求体包含 `max_seconds: 20`，页面上不存在第二个时长字段

### Requirement: 歌曲详情右侧面板

歌曲详情 MUST 以右侧浮动玻璃面板呈现：`#view-detail` 绝对定位于 `#main` 右缘（`position: absolute`；距顶/右/底各 12px，纵向与页面等高），宽度 360px，`border-radius: var(--radius-card)`。面板 MUST 为高斯模糊玻璃材质：背景为 `color-mix` 从 `var(--bg-raise)` 派生的半透明色 + `backdrop-filter` 模糊（不引入新的硬编码色值），以 1px `var(--line-soft)` 描边，z-index 低于 `#modal`；不支持 `backdrop-filter` 时 MUST 回退为不透明 `var(--bg-raise)`。打开/关闭 MUST 仅以 `transform: translateX()` 过渡，时长不超过 0.18s。详情 MUST NOT 再表现为整页视图，主区当前视图（创作/音乐库）MUST 保持可见与可交互。

#### Scenario: 打开详情面板

WHEN 用户点击歌曲行的详情区域
THEN 详情面板从右缘滑入，主区列表不切换、不挤压，可继续点击其他歌曲

#### Scenario: 面板内切换歌曲

WHEN 面板开启中用户点击另一首歌曲
THEN 面板内容原地渲染新歌曲，不发生页面导航

#### Scenario: 关闭面板

WHEN 用户点击面板右上角 × 按钮或按 Esc
THEN 面板滑出关闭，主区视图保持原状

### Requirement: 面板窄宽版式

面板内详情 MUST 纵向排列：封面正方形居中（宽 ≤240px、1:1、圆角 `var(--radius-row)`）置顶，其下依次为操作行（既有 `.dact` 按钮组）、标题/艺人/风格/元信息、歌词/乐谱 tabs；tabs 与乐谱编辑器 MUST 自适应面板宽度；面板内容超高时 MUST 内部滚动（`overflow-y: auto`），底部播放条不被遮挡。

#### Scenario: 窄宽 hero

WHEN 面板展示一首带封面的歌曲
THEN 封面为正方形居中位于面板顶部，操作行与信息区位于封面下方，无横向 hero 布局

### Requirement: 生成歌曲信息展示

面板 MUST 为生成歌曲展示：风格卡片（标题、`style_original ?? style` 文本、复制按钮、英文标签 tooltip）、歌词与乐谱 tabs（维持现状）、技术详情（含转谱报告行与生成参数行）。

#### Scenario: 风格卡片

WHEN 面板展示一首有 `style_original` 的歌曲
THEN 风格卡片显示中文原文，右上角复制按钮点击后复制该显示文本，tooltip 保留英文标签

#### Scenario: 转谱报告

WHEN 歌曲发生过 Vocal→Ins 转谱（`transfer` 摘要或 `tech["transfer.json"]` 存在）
THEN 技术详情出现「转谱」行，显示人声音符数与移入 Ins 后的音符数

#### Scenario: 生成参数

WHEN 歌曲的 `request.json` 含 `cfg_scale` 或 `vocal_gender`
THEN 技术详情展示对应参数行；已展示的 `sampling`/`seed`/`backend`/`lora` 不重复

#### Scenario: 上传条目不受影响

WHEN 面板展示一条上传的音频
THEN 维持现有信息与占位文案，不做歌词/风格推断

### Requirement: 程序化封面艺术

歌曲封面 MUST 由前端确定性程序化生成：以歌曲 id 的哈希为种子（`hashCode` → `mulberry32`），在 Canvas 上绘制深色基底渐变、流场笔触（2–3 个种子化强调色）、径向暗角与胶片颗粒，导出 dataURL 作背景图。生成 MUST 离线完成，MUST NOT 发起任何网络请求或依赖服务端图片资源。同一歌曲 id MUST 始终得到相同封面（跨刷新、跨会话、跨展示位置一致）。封面覆盖全部展示位置：列表行、音乐库网格、详情面板、播放条，尺寸/圆角/布局 MUST 保持不变。Canvas 不可用时 MUST 回退为既有双色渐变，保证封面始终可见。

#### Scenario: 同一首歌封面稳定

WHEN 刷新页面或切换视图后再次查看同一首歌
THEN 其封面与之前完全一致

#### Scenario: 不同歌曲封面各异

WHEN 并排展示多首歌曲
THEN 各封面因 id 种子不同而各异，无重复色板感

#### Scenario: 离线可用

WHEN 应用在无网络环境运行
THEN 所有封面正常显示，无外部请求

#### Scenario: 缩略尺寸可辨

WHEN 封面以 84px 列表行或 46px 播放条尺寸展示
THEN 纹理仍可辨识，不糊成纯色块

#### Scenario: 回退

WHEN Canvas 上下文不可用
THEN 封面回退为既有双色渐变，界面与布局不变

### Requirement: 设置弹窗分组布局

设置弹窗 MUST 由分组构成（创作默认 / 生成行为 / 模型与性能 / 界面 / 高级与维护 / 状态），分组以 12px 小标题（13px、`--text-3`、字重 600）与 `--line-soft` 细分隔呈现；分组内各行 MUST 沿用既有 `.set-row` / `.set-seg` / `.set-input` / `.set-note` 组件，MUST NOT 引入新的行控件形态。弹窗 MUST 维持现有宽度、圆角与内部滚动行为。

#### Scenario: 分组标题

WHEN 打开设置弹窗
THEN 各设置项按组归位，组标题与小分隔线可见，行视觉与旧版逐行一致

#### Scenario: CUDA 专属项隐藏

WHEN 在非 CUDA 设备上打开设置
THEN FP8 量化与 AR 卸载行不显示，其余分组布局不受影响

### Requirement: 上传条目的重建入口

上传条目的详情面板 MUST 提供「YuE2 重建」操作入口，复用既有 `.dact` 按钮模式（尺寸、圆角、配色与其他详情操作一致）；MUST NOT 改变面板布局结构、新增组件形态或修改任何设计令牌。该入口 MUST NOT 出现在非上传（生成歌曲）条目的详情中。实施后既有基线截图（取景为歌曲条目）MUST 无差异。

#### Scenario: 上传条目详情

WHEN 打开一条上传音频的详情面板
THEN 操作行内出现「YuE2 重建」按钮，视觉与相邻 `.dact` 按钮一致

#### Scenario: 生成歌曲详情不受影响

WHEN 打开一首生成歌曲的详情面板
THEN 不出现重建按钮，面板与冻结基线逐像素一致

### Requirement: 下载入口统一呈现

歌曲行、详情面板与右键菜单中的音频下载入口 MUST 统一使用下载图标（Phosphor `ph-download`）与「下载 / Download」文案；MUST NOT 再使用分享图标/「分享」文案。按钮的形态、尺寸、配色与布局 MUST 保持不变，下载行为（`/api/songs/{id}/audio`）MUST 不变。

#### Scenario: 歌曲行下载入口

WHEN 播放就绪的歌曲出现在工作区/音乐库列表
THEN 行内按钮显示下载图标与「下载」文案，点击触发音频下载

#### Scenario: 详情面板与右键菜单

WHEN 打开歌曲详情面板或行右键菜单
THEN 对应入口均显示下载图标；tooltip/菜单文案为「下载」

### Requirement: 侧栏「模型」导航与模型页

侧栏 MUST 在「音乐库」与用户区之间新增「模型」导航项（Phosphor `ph-hard-drives` 图标、复用 `.sb-item` 既有模式）。对应 `#view-models` 页面 MUST 承载于 `#main` 内部（不新增顶层栏、不改变三栏与底栏结构）。页面 MUST 复用既有组件模式：分段控件（`.set-seg`）、卡片、进度条，MUST NOT 引入与冻结风格冲突的新组件形态。

#### Scenario: 打开模型页

WHEN 用户点击侧栏「模型」
THEN 主区显示模型清单页，创作面板隐藏、三栏与底栏不变；「模型」项呈选中态

#### Scenario: 基线更新

WHEN 本变更实施完成
THEN `docs/ui-baseline/{en,zh}/` 全部页面因侧栏新增项重截，并新增 `models.png`（en/zh 各一张）

### Requirement: 重渲染保持滚动位置

凡滚动容器位于被整体重建的 DOM 子树内（模型页 `.mdl-scroll`、详情面板 `#detail-content`、设置弹窗 `#modal`），重渲染 MUST 保留并恢复用户的滚动位置；同一视图的周期性刷新（轮询）MUST NOT 将滚动位置重置为顶部。切换到不同实体（如详情面板换另一首歌）时 MAY 重置为该视图的初始位置。内容与上次渲染完全一致时 SHOULD 跳过重建以避免无谓的 DOM 抖动。

#### Scenario: 模型页轮询

WHEN 用户在模型页滚动到任意位置并停留（含下载进行中）
THEN 跨过任意次轮询后滚动位置保持不变

#### Scenario: 生成中的详情面板

WHEN 用户在详情面板浏览长歌词且该歌曲正在生成（状态周期性变化触发软刷新）
THEN 滚动位置保持不变；点击另一首歌打开时面板回到顶部

#### Scenario: 设置弹窗

WHEN 用户滚动设置弹窗到底部并点击某项设置
THEN 弹窗刷新后仍停留在原滚动位置

### Requirement: 辅助按钮覆盖前确认

创作面板的歌词示例按钮（✨）MUST 在目标输入框非空时先经确认对话框（复用既有 `confirmDialog` 组件）取得用户确认后才覆盖内容；输入框为空时 MUST 直接填充。风格魔法棒按钮：牌堆模式（未配置 LLM）下 MUST 遵守同样的「非空先确认、空则直接填充」；LLM 增强模式下 MUST 以「增强结果预览确认」实现覆盖前确认（见「魔法棒 LLM 增强交互」），风格框为空时 MUST 提示而非填充。各确认文案 MUST 两语（en/zh）齐备。

#### Scenario: 非空字段被覆盖

WHEN 用户已在歌词框输入内容后点击 ✨
THEN 弹出「替换歌词？」确认；取消则内容不变，确认则以示例歌词替换

#### Scenario: 空字段直接填充

WHEN 歌词框为空时点击 ✨，或未配置 LLM 时风格框为空点击魔法棒
THEN 直接填入示例歌词 / 示例牌堆，不弹确认

### Requirement: 示例内容来源真实数据

歌词示例按钮 MUST 优先从后端示例数据（`/api/examples` 的 `lyrics` 列表，含中文条目）中随机选取；后端不可用或列表为空时 MUST 回退到内置兜底示例。风格魔法棒的每组建议 MUST 通过内置词典可翻译（中文组不得含未收录词条）。

#### Scenario: 中文示例可达

WHEN 后端示例可用且用户点击 ✨
THEN 存在选中中文示例歌词的可能（示例池含中文条目）

#### Scenario: 中文建议组可翻译

WHEN 用户点选任一中文建议 chips 或整组填入风格框
THEN 生成时全部词条可经词典翻译为英文标签，无未收录残留

### Requirement: 侧栏「LLM 配置」导航与配置页

侧栏 MUST 保留「LLM 配置」导航项（`ph-robot`）。`#view-llm` MUST 承载于 `#main` 内部，复用既有组件模式（`.set-input` / `.set-seg` / `.mdl-card` / `.mdl-row` / pill 与 ghost 按钮 / `.set-note`），由三部分组成：

1. **顶部偏好区**：「当前使用」（enabled 供应商下拉 + 「不使用」）、「增强输出语言」（中文词表 / English tags）、「超时（1–60 秒）」；
2. **供应商列表**：每行复用 `.mdl-row` 模式——名称、preset 名、默认模型、掩码 key、启用开关，行内 [测试] [编辑] [删除]；列表上方「新建」按钮；新建/编辑以既有 `#modal` 承载表单（名称 / 预设下拉——切换时自动填充名称与 base_url、用户手改过的名称 MUST NOT 被覆盖 / 接口地址 / API Key 仅掩码占位 + 「清除」 / 「拉取模型」按钮 + 模型候选下拉（允许手输；base_url 变化清空候选；拉取失败 MUST NOT 清掉手输值）/ 启用开关）；保存失败 MUST 就地反馈且不关闭弹窗；
3. **试聊面板**：见「试聊面板版式」与「试聊对话交互」。

MUST NOT 引入与冻结风格冲突的新组件形态；密钥 MUST NOT 回显明文。

#### Scenario: 打开配置页

WHEN 用户点击侧栏「LLM 配置」
THEN 主区显示三部分版式（偏好区 / 供应商列表 / 试聊面板），三栏与底栏不变，「LLM 配置」呈选中态

#### Scenario: 预设切换自动填充

WHEN 在弹窗中将预设切到「DeepSeek」
THEN 名称与 base_url 自动填充；若用户已手改名称则保持不变

#### Scenario: 基线更新

WHEN 本变更实施完成
THEN `docs/ui-baseline/{en,zh}/llm.png` 重截为新版式，其余页面无变化

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

### Requirement: 试聊面板版式

试聊面板 MUST 为面板内两栏：左侧固定 208px 会话列表（顶部「新建」整宽按钮、其下「最近会话」小标签与可滚动列表；条目含标题（单行省略）与更新时间，选中态使用既有令牌的低对比高亮，hover 显示删除入口；空态提示），右侧为对话区（消息列 max-width 760px 居中、内部滚动；底部输入卡）。输入卡 MUST 为带边框圆角卡片：多行文本域（最小约 60px、最大约 180px 自适应）+ 底栏（**右下角为模型选择器**，其右侧为发送/停止按钮）+ 卡片下方一行提示（Enter 发送 · Shift+Enter 换行 · 对话仅存本机）。模型选择器按钮 MUST 显示 `供应商 · 模型`（单行省略、max-width 约 230px）；点击 MUST 向上弹出约 280px 宽的弹层（供应商列表 / 模型快捷选项列表（可滚动、选中态）/「选择模型」手输 / 「拉取模型」按钮 / 错误提示）。消息 MUST 为：用户 = 右对齐气泡（圆角 `16px 16px 4px 16px`、14px），助手 = 无气泡正文（行高 1.8）。全部样式 MUST 复用既有令牌与组件语言，MUST NOT 引入新的硬编码主题色。

#### Scenario: 版式呈现

WHEN 在 1440 宽度下打开配置页
THEN 试聊面板呈两栏（左 208px 会话列、右对话区），消息列居中且内部滚动，输入卡与提示行位于底部

#### Scenario: 模型弹层

WHEN 点击输入卡右下角的模型选择器
THEN 向上弹出弹层；切换供应商后模型候选刷新且重置为该供应商默认模型

### Requirement: 试聊对话交互

规则：**发送**——Enter 发送、Shift+Enter 换行（含 IME composition 保护）；空输入或流式进行中 MUST 禁用发送；流式进行中发送按钮变为**停止**。**流式**——助手气泡逐字追加；停止 MUST 中断流并保留已收内容（服务端落盘部分回复）。**会话**——新建后自动选中；切换 MUST 加载其消息；删除 MUST 经确认；未选中会话时发送禁用并提示。**模型**——弹层选择 MUST 写回当前会话（provider/model）。**提示与错误**——无激活供应商且会话未指定模型时输入禁用并提示先配置；错误 MUST 在对话区内以可读提示呈现并保留已收内容；刷新后会话与消息 MUST 保留（读本机存储）。全部文案 MUST 两语（en/zh）齐备。

#### Scenario: 流式往返

WHEN 在选中的会话中输入并发送
THEN 用户气泡即时出现，助手气泡逐字追加至完成，期间发送禁用、停止可用

#### Scenario: 停止保留已收

WHEN 流式输出中途点击停止
THEN 流中断、已显示内容保留并已落盘，输入恢复可用

#### Scenario: 键盘规则

WHEN 输入框中按 Enter（无 Shift）
THEN 发送；按 Shift+Enter 则换行不发送

#### Scenario: 会话切换与删除

WHEN 切换会话后再打开旧会话
THEN 各自消息完整呈现；删除会话经确认后从列表移除

#### Scenario: 刷新保留

WHEN 刷新页面后重新进入配置页
THEN 会话列表与选中会话的消息与刷新前一致

#### Scenario: 无激活供应商

WHEN 无激活供应商且会话未指定模型
THEN 输入禁用并提示先配置供应商

### Requirement: 供应商编辑弹窗版式

LLM 配置的供应商新建/编辑 MUST 以既有 `#modal` 承载**对话框版式**：每行为「标签列 + 控件列」——标签列固定宽（约 92px）、控件列占满剩余宽度（输入框全宽；不再沿用页面级「标签左、控件贴右缘」的 `.set-row` 排法）。「默认模型」行 MUST 为输入框 + 「拉取模型」按钮同行；拉取成功后 MUST 出现「已拉取模型」下拉（复用 `openDrop`；选中即回填模型输入框；模型为空时自动采用第一个）；「启用」MUST 使用既有 `.switch` 开关；底部 MUST 为右对齐的「取消 / 保存」按钮行（保存为主按钮）；编辑态 MUST 提供「清除 Key」。

页面与弹窗中以 `openDrop` 打开的下拉，其触发器 MUST 标注 `data-drop-opener`——全局「点外关闭」监听器以此判定；未标注的触发器会在打开的同一次点击中被立即收起（真实鼠标点击不可用，JS `.click()` 走查无法发现）。

#### Scenario: 弹窗版式

WHEN 打开「新建供应商」
THEN 表单为标签列 + 控件列布局，默认模型与「拉取模型」同行，底部为右对齐的取消/保存按钮行，启用为开关

#### Scenario: 已拉取模型下拉

WHEN 拉取模型成功
THEN 出现「已拉取模型」下拉；选择某项后模型输入框同步回填

#### Scenario: 下拉点击保持展开

WHEN 真实点击「平台预设」「当前使用」「已拉取模型」任一触发器
THEN 下拉打开并保持展开，直到选择某项或点击外部

#### Scenario: 编辑回填

WHEN 编辑既有供应商
THEN 各字段回填（API Key 仅掩码占位）、开关反映启用态、出现「清除 Key」
