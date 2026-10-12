# Spec Delta: web-ui-design（冻结基线的显式修订）

## ADDED Requirements

### Requirement: 上传条目的重建入口

上传条目的详情面板 MUST 提供「YuE2 重建」操作入口，复用既有 `.dact` 按钮模式（尺寸、圆角、配色与其他详情操作一致）；MUST NOT 改变面板布局结构、新增组件形态或修改任何设计令牌。该入口 MUST NOT 出现在非上传（生成歌曲）条目的详情中。实施后既有基线截图（取景为歌曲条目）MUST 无差异。

#### Scenario: 上传条目详情

WHEN 打开一条上传音频的详情面板
THEN 操作行内出现「YuE2 重建」按钮，视觉与相邻 `.dact` 按钮一致

#### Scenario: 生成歌曲详情不受影响

WHEN 打开一首生成歌曲的详情面板
THEN 不出现重建按钮，面板与冻结基线逐像素一致
