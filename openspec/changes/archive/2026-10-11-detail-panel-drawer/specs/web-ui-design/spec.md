# Spec Delta: web-ui-design（冻结基线的显式修订）

## ADDED Requirements

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
