# Proposal: detail-panel-drawer

## Why

点击工作区/音乐库中的歌曲后，当前实现是整页切换到 `#view-detail`（带 Back 按钮的新页面），而 Suno 的行为是在**右侧滑出详情面板**，列表保持可见、可继续点击切换。用户明确要求对齐 Suno 这一交互，并提供参考截图（已存 `ref-suno/detail-panel.png`）。

## What Changes

**本提案包含视觉变更（按 `web-ui-design` 规格显式声明）**，影响范围：歌曲详情的呈现容器与交互；详情信息内容不变（歌词/风格展示增强为另案，暂不实施）。

参照 `ref-suno/detail-panel.png` 的面板形态：

1. **详情改为右侧浮动玻璃面板**：`#view-detail` 从 `#main` 的整页视图改为浮于 `#main` 右缘的圆角玻璃面板——`position: absolute`，距顶/右/底各 12px（纵向与页面等高），宽 **360px**，`border-radius: var(--radius-card)`（20px）；**高斯模糊玻璃材质**：背景为令牌派生的半透明色 `color-mix(in srgb, var(--bg-raise) 72%, transparent)` + `backdrop-filter: blur(18px) saturate(1.3)`（不引入新硬编码色值），1px `var(--line-soft)` 描边；滑入/滑出仅用 `transform: translateX()` 过渡（≤0.18s，遵守「动效克制」白名单）。底部播放条不受影响。
2. **面板内版式**（自上而下，对齐参考图）：
   - × 圆形关闭钮，面板内右上角（替代现有 Back 按钮）；
   - 封面正方形居中（宽 ≤240px，圆角 `var(--radius-row)`），保留封面上的编辑浮钮；
   - 操作行（既有 `.dact` 按钮组：播放/remix/edit/点赞/分享/删除等，内容不变）；
   - 标题、艺人、风格、元信息（既有字段不变）；
   - 歌词/乐谱 tabs 与编辑器，宽度自适应面板；
   - 面板内容超高时内部滚动（`overflow-y: auto`）。
3. **交互模型**：
   - 点击歌曲行（`data-action="detail"`）打开面板；主区当前视图（创作/音乐库）**保持不变**，列表继续可见可交互。
   - 面板开启中点击另一首歌 → 内容原地切换（复用 `renderDetail`），无导航发生。
   - 关闭方式：× 按钮与 Esc 键；删除正在展示的歌曲时自动关闭。
4. **生成歌曲信息展示增强**（参考图 Styles 卡片的对应实现，仅针对生成歌曲）：
   - **风格卡片**：风格从信息区的一行文本升级为独立圆角卡片（对齐参考图 Styles 卡片）——标题「风格」、内容显示原文（`style_original ?? style`）、右上角复制按钮（复制当前显示文本）、tooltip 保留英文标签；
   - **转谱报告**：歌曲发生过 Vocal→Ins 转谱时（`transfer` 摘要或 `tech["transfer.json"]` 存在），在技术详情中新增「转谱」行：人声音符 N→0、Ins 音符数、保留原 Ins 数；
   - **生成参数补全**：技术详情补充 `request.json` 中尚未展示的参数——`cfg_scale`、`vocal_gender`（存在时）；`sampling`/`seed`/`backend`/`lora`/`truncated` 已有；
   - **歌词**：维持现有歌词 tab 展示，不改。
   - 服务端：`song_detail` 的 tech 读取列表加入 `transfer.json`。
5. **状态逻辑**：废弃 `state.view === "detail"` 与 `state.detailFrom`（详情不再是路由级视图）；`state.detailId` 非空即面板开启。轮询软刷新、删除联动、加载失败回退等既有行为平移到面板模型。
6. **非目标（Non-goals）**：
   - 不改三栏布局与栏宽；不改播放条；不做面板外点击关闭；不做移动端适配；
   - 不做 Suno 面板中的 Weirdness/Style Influence 等本模型不存在的参数；
   - **上传音频的歌词/风格展示明确不做**：现有探索结论——上传音频的歌词需要人声转写（ASR），仓库无此能力（可行路径为引入 Whisper）；风格提示词需要自动打标（仓库 MERT 仅覆盖旋律/结构），可行路径为 LLM 生成或手动编辑字段。两项均超出本提案范围，上传条目维持现有占位展示。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `web-ui-design`: 追加「歌曲详情右侧面板」作为冻结基线的显式修订——容器形态（浮动圆角面板、360px、transform 滑动）、交互模型（就地打开/切换/关闭）、面板内版式规则。

## Impact

- **代码**：`web/static/index.html`（`#view-detail` 头部 Back → × 关闭钮）、`web/static/styles.css`（面板定位/玻璃材质/过渡 + hero 纵向版式 + 风格卡片）、`web/static/app.js`（`runAction("detail")`、轮询刷新、删除联动、`detailFrom` 清理、Esc 监听、renderDetail 增加风格卡片/转谱行/参数行）、`web/server.py`（`song_detail` tech 读取 `transfer.json`）、`web/static/i18n.js`（关闭钮 tooltip、复制按钮与转谱行文案，en/zh）。
- **参考资产**：`ref-suno/detail-panel.png`（用户提供的 Suno 面板截图，已入库）。
- **基线截图**：`docs/ui-baseline/{en,zh}/detail.png` 重截（面板开启态）；create/library/settings 基线不变（面板关闭态与现状像素一致），实施后对照核查。
- **测试**：无 pytest 前端断言；以浏览器实测（打开/切换/关闭/Esc/删除联动/生成中进度刷新）+ 基线对照为验收。
- **风险**：`detailFrom` 被多处引用（导航高亮、失败回退），清理时须 grep 全量替换；面板开启时生成中歌曲的进度刷新（`renderDetail(id, soft)`）须保持工作。
