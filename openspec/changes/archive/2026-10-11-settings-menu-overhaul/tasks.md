# Tasks: settings-menu-overhaul

## 1. 服务端：设置字段与端点

- [x] 1.1 `web/server.py` SettingsUpdate 扩展 11 个新字段 + 校验（非法 422；`mlx_variant` 校验为已安装变体，动态扫描 `models/YuE2-3B-MLX/*/model.safetensors`）；`get_settings`/`state` 返回全部新字段、已安装变体列表与建议默认值；验证：curl 逐字段合法/非法请求
- [x] 1.2 `mlx_variant` 接入：`MLX_VARIANT` 硬编码改为读设置（`_generate_mlx` 命令组装与 `mlx_available()` 判定；`/api/state` 下发当前变体与已安装集合）；验证：提交未安装变体返回 422、切到 bf16 生成一首短歌正常
- [x] 1.3 `default_backend` 接入 `queue_song` 的 backend 回退（显式参数优先，非法/不可用回退 torch）；验证：不传 backend 的新歌使用默认
- [x] 1.4 存储端点：`GET /api/storage`（outputs/uploads/latent 合计与文件数）与 `POST /api/storage/cleanup`（删 latent.npy，返回释放字节）；验证：人工造 latent 文件后调用计数正确
- [x] 1.4b decoder 三档：`tools/download_extras.sh` 增加 `Mothersuperior/YuE2-Vae-merge-0.666` → `models/YuE2-Vae-merge/`；服务端 `decoder∈{default,legacy,merge}` 校验（缺权重 422 附提示）+ `_generate`/`_redecode` 的 vae 档位解析；验证：下载后切 merge 生成短歌、未下载时 422
- [x] 1.4c MLX 变体清单确认：bf16 已本地转换完成（7.0GB，烟测通过），设置应显示 {bf16, 8-bit}；验证：`get_settings` 返回两档
- [x] 1.4d `tools/download_mlx.sh` 头部注释补变体说明：bf16 自转命令（`convert.py --model ../YuE2-3B --vae ../YuE2-Vae --output bf16`，不加 `-q`；4bit 用 `-q --bits 4`）+ 变体目录约定；验证：按注释从零可复现转换
- [x] 1.4e 实测数据留档：bf16 vs 8-bit vs torch 速度对比（20s 歌两轮：8bit ~16-18s / bf16 ~28-29s / torch ~61s）写入同一注释区；验证：数字与本次测量一致
- [x] 1.5 服务端测试：新字段校验用例入 `tests/`；全量 pytest 绿色

## 2. 前端：设置弹窗分组重构

- [x] 2.1 `openSettings` 重排为六分组（创作默认/生成行为/模型与性能/界面/高级与维护/状态），分组标题样式入 `styles.css`（`--line-soft` 分隔 + 小标题）；验证：视口内滚动正常
- [x] 2.2 新控件接线：默认后端、默认模式、默认时长、默认 CFG、风格语言（复用现有 seg 模式）；界面语言/启动页面/默认排序/减少动效；自动播放/通知（通知首次请求权限，拒绝回弹+toast）/刷新间隔；**MLX 量化变体行（已安装集合、当前档位、未装变体不出现）**；decoder 三段（含 merge 置灰逻辑）；验证：逐项修改后重开弹窗持久、刷新页面仍生效
- [x] 2.2b 前端变体展示三处：①创作面板模型 pill 下拉（`app.js:753-758`）MLX 选项标签改为动态变体（模板化 `model.engineMlx`，en/zh 双份 i18n）；②详情面板技术信息「引擎」行（`app.js:400`）优先读 `tech["result.json"].backend`（MLX 结果已写 `mlx-<variant>`），存量歌曲回退 "MLX · 8-bit"；③设置切换变体后 pill 文案同步刷新；验证：切 bf16 后 pill 与生成歌曲的技术信息行均显示 bf16、切回 8-bit 复原（纯文案变化，无新控件）
- [x] 2.3 i18n：约 30 条新 key（en/zh）；验证：两语言下无漏文案

## 3. 前端：默认值应用与行为

- [x] 3.1 启动时拉取设置→应用：`start_view`、`default_mode`、`state.backend`（含 mlx_available 回退）、`state.sort`、创建面板默认值与 clear-form/重置预填；验证：改设置后刷新，创作面板初始状态正确
- [x] 3.2 行为钩子：任务完成检测（状态迁移）→ 自动播放/桌面通知；`poll_interval` 重建刷新定时器；`reduce_motion` body class；验证：生成一首短歌观察自动播放与通知；间隔改 10s 后请求频率下降
- [x] 3.3 存储面板与清理按钮（二次确认）+ 重置设置（二次确认，恢复出厂默认后 UI 立即刷新）；验证：清理前后占用数字变化

## 4. 实测与基线

- [x] 4.1 设置弹窗 en/zh 截图对照：分组布局、全部行可见、CUDA 专属项在本机隐藏
- [x] 4.2 重截 `docs/ui-baseline/{en,zh}/settings.png`；其余基线不受影响（默认行为等价 + 封面等不变），对照确认
- [x] 4.3 生成一首短歌做行为回归（默认后端 MLX 生效、无设置异常）

## 5. 校验与归档

- [x] 5.1 `openspec validate settings-menu-overhaul --strict`；归档；`codegraph sync`
