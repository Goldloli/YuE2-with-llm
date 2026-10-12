# Design: detail-panel-drawer

## 参考形态（ref-suno/detail-panel.png 实测）

Suno 右侧面板的关键视觉事实（全分辨率裁剪核对）：

- **浮动圆角卡片**，非贴边直角抽屉：距视口顶/右/底有边距，圆角大（≈20px+），底色比主区略亮；
- 宽约视口 11%（折合 1440px 视口 ≈ 320–360px）；
- × 圆形关闭钮在面板内右上角；
- 封面正方形居中（约占面板宽 2/3），圆角；
- 操作行为胶囊按钮行（播放/点赞/评论/分享）；
- 标题左对齐居中偏下，下方依次为 Caption、Remix/Edit 主按钮、Styles 卡片（后两者属信息增强，本提案不做）。

## 现状与目标对照

| | 现状 | 目标 |
|---|---|---|
| 打开详情 | `showView("detail")` 整页替换，Back 返回 | 右侧浮动面板滑入，列表保持可见 |
| 切换歌曲 | 返回列表再点 | 直接点另一首，面板内容原地切换 |
| 详情版式 | 横向 hero（264px 封面 + 右侧信息） | 纵向：封面居中、操作行、信息、tabs |

## 关键决策

### 决策 1：覆盖式浮动面板，而非挤压式布局

挤压式需要 width 动画，违反「动效克制」的过渡属性白名单（仅 opacity/background/transform/border-color），且引发布局抖动。覆盖式：`#main` 加 `position: relative`，面板 `position: absolute` 贴右缘（含 12px 浮动边距），`transform: translateX(calc(100% + 12px)) → 0` 滑入。列表保持全宽、布局零抖动。

### 决策 2：360px、全高等边距、玻璃拟态、复用令牌

宽度 360px（对齐参考图比例，与创作面板 450px 形成层级）；距顶/右/底各 12px，纵向与页面等高。**玻璃材质**：`background: color-mix(in srgb, var(--bg-raise) 72%, transparent)` + `backdrop-filter: blur(18px) saturate(1.3)`——半透明底色由 `--bg-raise` 令牌派生（`color-mix`，不引入平行硬编码色值，符合「设计令牌冻结」），后方列表内容透过面板模糊可见，层次与 Suno 面板一致；描边 1px `var(--line-soft)`。z-index 高于列表、低于 `#modal` 与 `#ctx-menu`。`backdrop-filter` 为静态效果，不涉及过渡属性，不违反「动效克制」；单一面板一处模糊，性能开销可忽略。降级：`@supports not (backdrop-filter: …)` 时回退为不透明 `var(--bg-raise)`。

### 决策 3：复用 `renderDetail` 与既有 DOM/组件

`#view-detail`、`#detail-content`、`renderDetail(id, soft)`、`.dact` 操作行、tabs/panes、乐谱编辑器全部保留，只换容器定位与 hero 版式 CSS。信息内容零变化（Styles 卡片/Caption 等属另案）。关闭钮复用 `.cp-circle` 圆形按钮模式 + `ph-x` 图标。

### 决策 4：状态模型简化

- `state.detailId` 非空 = 面板开启；`showView` 不再接受 `"detail"`；`state.detailFrom` 删除。
- 导航高亮（`data-nav`）不再被详情态干扰——当前视图始终是 create/library 之一。
- 软刷新条件 `state.detailId && state.view === "detail"` → `state.detailId` 非空。
- `loadVariant`/`openCover`/`openEdit` 等从详情进入创作的入口：成功后关闭面板再 `showView("create")`。
- 加载失败：关面板 + toast（原为返回 detailFrom）。
- Esc 关闭挂在 document keydown，仅在面板开启时生效。

### 决策 5：面板内版式

- `.detail-hero` 在面板内 `flex-direction: column`；`.detail-cover` 宽度 `min(240px, 100%)`、`aspect-ratio: 1`、居中（`margin: 0 auto`）；
- `.detail-title` 30px → 24px（窄宽适配，字体字重不变）；`.detail-pane` 去掉 `max-width: 780px`；
- `.score-editor` 宽度 100%；
- 面板整体 `overflow-y: auto`，内容超高内部滚动。

### 决策 6：生成歌曲信息展示（面板内容增强）

- **风格卡片位置**：置于信息区（标题/艺人/元信息）之后、tabs 之前，对应参考图 Styles 卡片位置；样式复用 `.cp-card` 家族观感（圆角 `var(--radius-card)`、底 `var(--card-soft)`）但以 `.detail-style-card` 独立类实现，避免与创作面板耦合。
- **复制语义**：复制当前**显示文本**（即 `style_original ?? style`，用户看到什么复制什么）；英文标签仅在 tooltip。复制成功走既有 toast 反馈（复用 `toast()`），不新增组件。
- **转谱行数据源优先级**：`d.transfer`（入队时转谱，歌曲记录字段）→ `tech["transfer.json"]`（生成时转谱，输出目录文件）。服务端把 `transfer.json` 加入 tech 读取列表即可打通两条路径，无需改 runner。
- **参数行**：只补 `request.json` 里有、界面尚未展示的（`cfg_scale`、`vocal_gender`）；`sampling` 已按 `k=v` 展示，不重复。MLX 与 torch 的 `request.json` 字段名一致（style/lyrics/cot/seed/cfg_scale/sampling）。
- **歌词不做内联改造**：维持 tab（面板窄，内联会把 tabs 挤出首屏）。
- **上传条目**：维持现状（占位文案）；ASR/自动打标超出本提案（见 proposal Non-goals）。

## 风险与缓解

- **`detailFrom` 残留**：grep 全量替换，实施后浏览器逐个验证入口（行点击、右键菜单、生成中点击、删除当前歌）。
- **面板遮挡列表右侧操作**：列表行操作位于行内左侧/中部，影响小；用户可关面板后再操作被遮挡行。
- **轮询刷新抖动**：`renderDetail(id, soft)` 的 sig 比对逻辑不变，仅改开启条件。
