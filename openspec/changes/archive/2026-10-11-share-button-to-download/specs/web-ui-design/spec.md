# Spec Delta: web-ui-design（冻结基线的显式修订）

## ADDED Requirements

### Requirement: 下载入口统一呈现

歌曲行、详情面板与右键菜单中的音频下载入口 MUST 统一使用下载图标（Phosphor `ph-download`）与「下载 / Download」文案；MUST NOT 再使用分享图标/「分享」文案。按钮的形态、尺寸、配色与布局 MUST 保持不变，下载行为（`/api/songs/{id}/audio`）MUST 不变。

#### Scenario: 歌曲行下载入口

WHEN 播放就绪的歌曲出现在工作区/音乐库列表
THEN 行内按钮显示下载图标与「下载」文案，点击触发音频下载

#### Scenario: 详情面板与右键菜单

WHEN 打开歌曲详情面板或行右键菜单
THEN 对应入口均显示下载图标；tooltip/菜单文案为「下载」
