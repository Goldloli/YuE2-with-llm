# Proposal: procedural-cover-art

## Why

Suno 每首歌有专属 AI 生成封面图；本项目当前封面是 12 组双色线性渐变的哈希换色（`coverStyle()`），观感平淡且重复明显。用户明确不要 AI 生成、不要联网抓图，选定**纯前端程序化生成**（Canvas 流场艺术）方案——离线、零依赖、每首歌确定性唯一。经 demo 对比（`compare/cover-options.png` 第 C 行）确认视觉方向。

## What Changes

**本提案包含视觉变更（按 `web-ui-design` 规格显式声明）**，影响所有展示封面的位置。

1. **程序化封面生成**：`app.js` 新增确定性 Canvas 艺术生成器——以歌曲 id 的哈希做种子（mulberry32 PRNG）：
   - 深色基底渐变（种子化色相）；
   - 约 400+ 条流场笔触（curl 场 + 2–3 个种子化强调色，低透明度叠画）；
   - 径向暗角；
   - 胶片颗粒（ImageData 噪声）。
   - 画布 256×256，导出 dataURL，缓存于内存（`Map<id, url>`），同一首歌跨会话稳定、跨位置复用。
2. **接入方式零侵入**：`coverStyle(id)` 保持函数签名与返回样式串的契约，内部改为返回 `background-image: url(dataURL); background-size: cover; background-color: <种子化基色>`——四处调用点（列表行、音乐库网格、详情面板、播放条）零改动；dataURL 未就绪或被禁用时回退现有渐变。
3. **性能**：首次需要某首歌封面时同步生成（单张毫秒级），随后全部命中缓存；列表轮询刷新不重绘已有 id。
4. **基线更新**：封面出现在全部页面，`docs/ui-baseline/{en,zh}/` 五张截图全部随视觉变更重截更新。
5. **非目标（Non-goals）**：
   - 不联网（Picsum 等在线图库方案已按用户决定排除）；
   - 不提取上传音频的内嵌封面（m4a `covr`/flac `PICTURE`）；
   - 不做「风格感知调色」（style 关键词→色相映射）；
   - 不改服务端：不放图片文件、不加 API；
   - 不改封面的尺寸、圆角、布局与其余任何样式。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `web-ui-design`: 追加「程序化封面艺术」作为冻结基线的显式修订——生成方式（确定性、离线、零依赖）、视觉构成（流场笔触/暗角/颗粒）、接入契约（`coverStyle` 返回样式串不变）与回退要求。

## Impact

- **代码**：`web/static/app.js`（新增生成器 ~90 行 + `coverStyle()` 改写 + 回退分支）；`web/static/styles.css` 不动（尺寸/圆角沿用）。
- **基线截图**：`docs/ui-baseline/{en,zh}/` × 5 张全部重截（封面为全局元素）。
- **测试**：无 pytest 前端断言；以浏览器实测（四处封面渲染、刷新后同一首歌封面不变、跨会话一致、缩略图清晰度）+ 基线对照为验收。
- **风险**：列表大量歌曲时首次生成的同步开销——以缓存与单张毫秒级生成缓解；视觉主体色相随机，极端色相（如高饱和黄绿）观感不佳时调参（色相范围限制在深色调域）。
