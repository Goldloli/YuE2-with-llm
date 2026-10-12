# Spec Delta: web-ui-design（显式修订）

## ADDED Requirements

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
