# Proposal: settings-menu-overhaul

## Why

设置弹窗目前是平铺的 4 个可调项（语言/解码器/推理后端/显存预算）+ 3 个状态行，而「默认用 MLX 后端」这类常用偏好每次都要在创作面板手动选。用户要求深入扩展设置菜单，把各类选项收进设置并分组呈现。

## What Changes

**本提案包含视觉变更（按 `web-ui-design` 规格显式声明）**，影响范围仅限设置弹窗：①平铺行改为**分组式布局**（分组小标题 + 既有 `.set-row` 行样式）；②新增多行设置项使弹窗变长（维持现有宽度与内部滚动）；③音频解码器由两段扩为三段分段控件（含 merge 未安装时的置灰态）。三项均不引入新组件形态；弹窗之外的界面零视觉变化。

按分组新增设置项（全部服务端持久化，重启后保留）：

### 创作默认（新建面板/重置表单时的初始值）

1. **默认推理后端** `default_backend`：MLX · 8-bit（推荐）/ PyTorch · MPS——创作面板模型选择器的初始值与 cover/edit/batch 未显式指定时的服务端回退默认；
2. **默认模式** `default_mode`：简单 / 高级——打开应用时创作面板的模式；
3. **默认时长上限** `default_max_seconds`：空（自动）/ 5–360 秒——高级模式时长字段的预填值；
4. **默认 CFG 强度** `default_cfg`：空（自动）/ 0–20——CFG 字段预填值；
5. **风格提示词语言** `style_language`：自动翻译 / 强制英文 / 原样直传——服务端已有此设置但未暴露 UI，本次补上。

### 生成行为

6. **完成后自动播放** `autoplay_on_complete`：开/关（默认关）——有任务从生成中变为完成时自动开始播放；
7. **完成后桌面通知** `notify_on_complete`：开/关（默认关）——浏览器 Notification API（首次开启时请求权限）；
8. **列表刷新间隔** `poll_interval`：1.5 / 3 / 5 / 10 秒——现状固定 1.5s。

### 模型与性能（保留现有项 + 新增）

9. **MLX 量化变体** `mlx_variant`：设置项**只列出本地已安装的变体**（`models/YuE2-3B-MLX/<variant>/model.safetensors` 存在者；**bf16 变体已在本机完成转换，当前集合 = {bf16, 8-bit}**）。替换 `server.py` 硬编码的 `MLX_VARIANT`，下个 MLX 任务生效。4bit 变体需用户自行转换（`convert.py --bits 4`）或下载后自动出现在选项中；未安装的变体在设置中不出现；
10. **前端展示当前变体**：创作面板的模型选择下拉（pill 弹层）中 MLX 选项的副标题 MUST 显示**当前激活变体**（如「MLX · bf16 — Apple-native」/「MLX · 8-bit — Apple-native」）而非写死 8-bit；设置弹窗的变体行同步显示已安装集合与当前档位。纯文案/动态文本变化（不新增控件、不改布局），不构成新视觉变更；
11. **音频解码器扩展为三档** `decoder`：默认 / 旧版（基准）/ **合并 0.666**（`Mothersuperior/YuE2-Vae-merge-0.666`，默认与 legacy 按 0.666/0.334 线性合并的权重——比默认更音乐性、比 legacy 更干净）。仅对 PyTorch 生成生效（MLX 用自带解码器，现有语义不变）；未下载 merge 权重时选项置灰并提示下载命令。`tools/download_extras.sh` 增加该权重（hf-mirror）；
12. 其余现有项原位保留：推理后端（CUDA 时）、FP8 量化与 AR 卸载（CUDA 时）、显存预算、环境自检。

### 界面

13. **启动页面** `start_view`：创作 / 音乐库；
14. **默认排序** `default_sort`：最新 / 最早 / 标题——列表排序器的初始值；
15. **减少动效** `reduce_motion`：开/关——开启后禁用过渡与动画（抽屉滑动、toast、旋转等即时切换）。

### 高级与维护

16. **存储占用**：显示 outputs / uploads 占用与中间文件（`latent.npy`）合计；「清理中间文件」按钮（带确认）删除各输出目录的 latent 文件——删除后该歌曲不能再「重混解码」，按钮文案与确认弹窗明确提示；
17. **重置设置**：一键恢复出厂默认（二次确认）。

### 非目标（Non-goals）

- 不做设置导入/导出 JSON；
- 不做风格翻译 LLM 端点（base_url/api_key）配置化——涉及密钥存储与连通性测试，另案评估；
- CUDA 专属项维持现状（本机 MPS 不显示）；
- 除「decoder 扩为三档」与「mlx_variant 改为读设置」两项既有项的扩展外，不改其他既有项的服务端行为与校验语义。

## Capabilities

### New Capabilities

- `app-settings`: 客户端偏好的持久化契约——字段定义、校验、默认值、生效时机（即时/下次任务）。

### Modified Capabilities

- `web-ui-design`: 追加设置弹窗的分组式布局、新增设置行与 decoder 三段控件为显式视觉变更（既有 `.set-row`/`.set-seg` 模式，无新组件形态）。

## Impact

- **代码**：`web/server.py`（SettingsUpdate 扩展与校验、`mlx_variant` 接入 `_generate_mlx`/`mlx_available`、queue 默认后端、存储统计与清理端点）、`web/static/app.js`（openSettings 分组重构 + 新控件接线、初始值应用、自动播放/通知/轮询间隔/减少动效/启动页面/默认排序）、`web/static/styles.css`（分组标题小样式）、`web/static/i18n.js`（约 30 条新文案 en/zh）。
- **基线截图**：`docs/ui-baseline/{en,zh}/settings.png` 两张重截；其余页面不受影响（设置默认为「现状行为」，除 `default_backend` 默认值建议为 MLX——见 design 决策）。
- **测试**：服务端新增字段的校验用例（非法值 422、默认值合并）；全量 `pytest` 保持绿色。
- **风险**：默认后端改为 MLX 后，未装 MLX 环境的机器需回退——`mlx_available()` 为假时前端忽略该默认并回退 PyTorch。
