# Spec Delta: web-ui-design（冻结基线的显式修订）

## ADDED Requirements

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
