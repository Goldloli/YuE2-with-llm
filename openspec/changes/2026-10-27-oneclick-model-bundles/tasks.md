# Tasks

## 1. 下载器小改（hf_download.py）

- [x] 1.1 `mlx-4bit` / `mlx-bf16` 模式也拉取 MLX 推理代码（MLX_CODE 列表）；新增 `vae` 细粒度模式（仅 YuE2-Vae 小文件 + model.safetensors）。验证：本机 `python tools/hf_download.py vae` 跑通（已存在则秒过 skip）；`mlx-4bit` 模式下 code 文件齐；`pytest tests/` 相关用例通过

## 2. 构建脚本（build_model_bundle.py）

- [x] 2.1 新建 `packaging/build_model_bundle.py`：TIERS 单一定义（平台 × 档位 → 下载模式列表 + 必需/禁用条目 + zip 预估体积），import 复用 `build_package.py` 的 stage_source/scan_forbidden/self_check/check_style_terms。验证：`python packaging/build_model_bundle.py --help` 正常，TIERS 可被 import
- [x] 2.2 实现磁盘预检（`shutil.disk_usage`，需求 = 档位预估 + 7.3 GiB 最大组件 + 1 GiB 余量，不足即非零退出并打印数值）。验证：人为抬高阈值运行，看到快速失败与清晰报错
- [x] 2.3 实现流式打包循环（逐组件：hf_download → STORED 追加进 zip64 → 删除原件）与分卷输出（≤1.9 GiB `.part-aa…` + 单一 `.sha256` 清单）；提供 `--use-local-models` 跳过下载直接用本机 `models/`（供本机验证）。验证：本机 `--use-local-models --platform win-x64 --tier standard` 产出分卷，`cat` 合并后 sha256 与原 zip 一致
- [x] 2.4 新增 pytest：TIERS 内容边界（win 档无 MLX 前缀、mini 档无 torch 3B）、分卷大小上限/命名连续/清单一一对应。验证：`pytest tests/test_model_bundle*.py` 通过
- [x] 2.5 磁盘预检按真实峰值收紧：`disk_need()` = `max(zip 预估 + 最大组件, 2 × zip 预估) + 2 GiB`（切分阶段 zip + 全部分卷是瓶颈），本地档不加组件；不足时打印需求/余量与清理指引。验证：新增 4 个单测（公式、14 GB runner 预算 11.2/12.8/16.8 GiB、失败/通过路径），旧公式对 win-x64/standard 虚高到 24.1 GiB

## 3. 冒烟扩展（smoke_package.py）

- [x] 3.1 增加 `--bundle <平台> <档位>` 模式：zip 条目级校验（必需条目在位且 STORED/大小匹配、禁用前缀缺席）+ 分卷级校验（大小上限、命名连续、sha256 清单逐卷核验），import TIERS 保持单一事实来源。验证：对 2.3 的产出跑通正例；手工删一个必需条目/改一个分卷字节，负例均非零失败

## 4. 首启与文档

- [x] 4.1 核实 `tools/bootstrap.py` / `tools/start.py` 在模型已就位时跳过下载；若缺失按「必需文件完整即跳过」补齐。验证：在含模型的暂存包目录运行启动流程，日志无下载行为、服务正常拉起
- [x] 4.2 `packaging/使用说明.md` 增补：分卷合并命令（macOS `cat`、Windows `copy /b`）、sha256 校验命令、各档位内存/磁盘要求与选择建议。验证：文档渲染正常，命令与产物命名逐字一致

## 5. CI workflow（oneclick-models.yml）

- [x] 5.1 新建 `.github/workflows/oneclick-models.yml`：`models-v*` tag → prepare 建草稿 release → matrix 并行构建 5 档 → 冒烟 → 上传分卷+清单 → publish 草稿转正式；`workflow_dispatch`（platform/tier 输入）→ 滚动 release `oneclick-models-latest`；头部注释成本提示（私仓 macOS 10×）。验证：YAML 语法与 actionlint 通过；`concurrency`/`permissions` 与现有 workflow 对齐
- [x] 5.4 标准 runner 只有 14 GB SSD：在 build job 加「按需释放磁盘」步骤——先用 `disk_need()` 对比实测余量，不足才删预装工具链（macOS Xcode/模拟器缓存 ≈30–40 GB，Windows Android/.NET 缓存），清理后仍不足则由预检快速失败。验证：actionlint 通过；本机按 14 GB 阈值模拟时 macOS mini/standard 跳过清理、win-x64/standard 触发清理
- [x] 5.2 dispatch 试跑 `win-x64 / standard`（成本最低路径）：release 资产齐全、冒烟日志绿、分卷合并后 zip 可用。验证：2026-10-27 run 40485808788 全绿（12m10s）——zipped 7.27 GiB→5 卷，条目冒烟 195 项、分卷冒烟 5 卷 + merged sha256=811841d6…，6 个资产已进 `oneclick-models-latest`；runner 实测空闲 109.9 GiB（预检 16.8 GiB 通过、清理步骤跳过）
- [x] 5.3 dispatch 试跑 `macos / mini`：观察磁盘预检数值与构建耗时，确认成本可接受。验证：2026-10-27 run 40488069140 全绿（3m47s）——zipped 3.89 GiB→3 卷，条目冒烟 197 项/9 个必需权重、分卷冒烟 3 卷 + merged sha256=356b08a3…；runner 实测空闲 96.2 GiB。首次 run 40487484848 构建冒烟全绿但上传步骤因 `$REL：`（全角冒号紧跟变量）在 macOS bash 3.2 下 unbound 失败，已修（commit 640713c）并新增 `tests/test_workflows.py` 守护

## 6. 收尾验证

- [x] 6.1 `pytest` 全绿
- [x] 6.2 `openspec validate 2026-10-27-oneclick-model-bundles --strict` 通过
- [ ] 6.3（用户确认后）打 `models-v1` tag 做首次全量正式发布，检查草稿→转正式流程与 5 档资产完整性。实测 runner 空闲 96–110 GiB，五档峰值（最大 `macos/full` 55.2 GiB）均在范围内，可全部交给 CI；macOS 3 个 job 按 10× 计费，`full` 档预计 12–20 分钟/个
