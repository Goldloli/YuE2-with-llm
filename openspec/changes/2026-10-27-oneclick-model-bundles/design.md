# Design: 2026-10-27-oneclick-model-bundles

## Context

现状约束（详见 proposal.md）：

- `packaging/build_package.py` 已有成熟的暂存→反扫→自检→打 zip 流程，`--with-models` 从**本地** `models/` 读权重（本地构建前提：模型已下好）；CI 的 `oneclick.yml` 只跑 slim 包。
- `tools/hf_download.py` 已有全部模型组件的下载清单（仓库/路径/字节数）、并发分块、断点续传与 `weights_manifest.json` sha256 校验；镜像可通过 `YUE2_HF_ENDPOINT` 覆盖。
- GitHub Release 单资产上限 2 GiB；模型包最小档约 4.5 GB，必须分卷。
- 仓库为私仓：macOS runner 分钟 10× 计费。
- 参考实现：xiaoheihe_crawler 的 `oneclick-release.yml`（tag → 草稿 release → 双平台并行构建+冒烟+上传 → 草稿转正式）。

## Goals / Non-Goals

**Goals:**

- CI 从零下载模型并产出 5 个档位的内嵌模型包（macOS：mini/standard/full；win-x64：standard/full），分卷 ≤1.9 GiB 上 Release。
- 构建过程磁盘峰值受控（流式：下一组 → 压入 zip → 删原件），磁盘不足时快速失败。
- 发布流复制参考项目的「草稿→转正式」，半成品对收件人不可见。

**Non-Goals:**

- 不改 slim 包构建与 `oneclick.yml`（既有行为保持不变）。
- 不做包内冒烟时全量解压/CRC 校验（26 GB 解压在校验价值与 macOS 分钟成本上不划算；下载侧 sha256 已逐文件校验）。
- 不做安装器/图形化合并工具；分卷合并用系统原生命令。
- Intel Mac、Linux 平台不在本期范围。

## Decisions

### D1：新脚本 `packaging/build_model_bundle.py`，复用而非改动 `build_package.py`

档位定义（TIERS dict：平台 × 档位 → hf_download 模式列表 + 必需/禁用条目）写在新脚本里，作为**单一事实来源**；`smoke` 侧 import 同一定义做校验。暂存、反扫、自检、词表校验通过 `sys.path` 同目录 import 复用 `build_package.py` 的 `stage_source` / `scan_forbidden` / `self_check` / `check_style_terms`。

备选：给 `build_package.py` 加 `--fetch` 模式。否决理由：slim 构建已验证稳定，混入「下载-打包-删除」状态机会让两个用例互相拖累；独立脚本 + 函数级复用改动面更小。

### D2：流式「下载 → STORED 追加 → 删除」控制磁盘峰值

CI 上没有预置模型，全量下载 + 全量打包意味着 2× 模型体积的磁盘需求（full 档 ≈ 52 GB），逼近 runner 磁盘红线。改为逐组件循环：

1. `python tools/hf_download.py <mode>` 下到仓库 `models/`（复用其现有 DEST 约定，不改下载器）；
2. 把该组件目录以 STORED 追加进同一个 zip（`zipfile` 支持增量追加，`allowZip64=True`）；
3. `shutil.rmtree` 删除该组件，再处理下一个。

磁盘峰值 ≈ max(zip 体积 + 单组件体积, 2 × zip 体积)：流式构建阶段是「未完成的 zip + 一个待删组件」，随后切分阶段必须让整份 zip 与全部分卷并存（分卷是 zip 的字节副本），后者才是瓶颈。构建前 `shutil.disk_usage` 预检按 `disk_need() = max(zip 预估 + 最大组件, 2 × zip 预估) + 2 GiB 余量` 判断（本地 `--use-local-models` 不含下载项），不足即以清晰报错退出并提示清理 runner 磁盘。GitHub 托管的标准 runner 只有 14 GB SSD，因此 workflow 先按同一公式对比实测余量，不足时才清理预装工具链（macOS 删 Xcode/模拟器缓存，Windows 删 Android/.NET 缓存），清理后仍不足即快速失败。

### D3：CI 直连 huggingface.co

`YUE2_HF_ENDPOINT=https://huggingface.co`：GitHub runner 在境外，直连 HF 的吞吐远好于 hf-mirror（镜像主要服务境内用户）。本机/境内使用场景不受影响（默认值不变）。

### D4：分卷用 Python 实现，合并用系统原生命令

构建侧：`build_model_bundle.py` 在 zip 完成后按 1_900_000_000 字节（< 2 GiB 上限，留余量）顺序切块写出 `<zip名>.part-aa/.part-ab/…`，边切边算各分卷 sha256，产出单一 `<zip名>.sha256` 清单。不依赖外部 `split`（Windows 无此命令）。

合并侧：分卷是 zip 的纯顺序字节切分，`cat a.part-* > a.zip`（macOS）/ `copy /b a.part-aa+a.part-ab+… a.zip`（Windows cmd）即可还原，系统解压工具直接可用。使用说明给出两条命令与 `shasum -a 256 -c` / `certutil -hashfile` 校验方法。

备选：zip 原生 multi-volume（`zip -s`）或 7z 分卷。否决理由：multi-volume zip 的解压工具兼容性差（Windows Explorer 不支持），7z 要求收件人装额外软件。

### D5：独立 workflow `oneclick-models.yml`，tag / 手动双触发

不动现有 `oneclick.yml`。新 workflow：

- `on: push tags ['models-v*']` + `workflow_dispatch`（inputs：`platform` ∈ all/macos/win-x64，`tier` ∈ all/mini/standard/full）。
- jobs：`prepare`（tag → 建草稿 release；dispatch → 确保 rolling release `oneclick-models-latest` 存在）→ `build`（matrix：2 平台 × 档位集合，tag 触发为全量 5 档，dispatch 按 inputs 过滤）→ `publish`（仅 tag 流：草稿转正式）。
- 每个 build job：checkout → setup-python → 磁盘预检 → `build_model_bundle.py` → 冒烟 → `gh release upload` 分卷+清单（`--clobber`）。
- workflow 头部注释写明成本：私仓 macOS 10× 分钟；tag 全量发布一次 ≈ 下载 50 GB / 5 个 job；日常单档用 dispatch。

备选：扩展现有 `oneclick.yml` 加 matrix 维度。否决理由：触发语义不同（push vs tag/手动），混在一个文件里互相牵制；参考项目也是滚动包与版本发布分文件。

### D6：冒烟分两级，均不解压数据

- zip 级：`zipfile.infolist()` 校验条目清单——档位必需条目在位（路径、`compress_type == ZIP_STORED`、声明大小匹配 TIERS 表）、禁用前缀缺席（沿用 slim 红线 + 平台/档位排除项）、`start.command`/`start.bat`/使用说明在位。
- 分卷级：逐分卷读流算 sha256 对照清单、单卷 ≤1.9 GiB、命名连续无缺口。

扩展 `packaging/smoke_package.py` 增加 `--bundle` 模式（import TIERS），而非另起脚本——冒烟入口保持单一。

### D7：hf_download.py 的小修正

`mlx-4bit` / `mlx-bf16` 模式目前不拉 MLX 推理代码（`generate.py`、`yue2_model.py` 等，`run()` 里仅 8bit 拉取），而 mini/full 档需要它们。改为所有 `mlx-*` 模式都拉取 MLX_CODE（几十 KB，无成本）。同时新增 `vae` 细粒度模式（仅 `YuE2-Vae` 小文件 + safetensors），供 macOS mini/standard 档使用，避免为拿 506 MB 的 VAE 去下载 7.3 GB 的 torch 主模型。

## Risks / Trade-offs

- [标准 runner 仅 14 GB SSD，macOS/full（切分峰值 ≈53 GiB）与 win-x64/full（≈25 GiB）放不下] → workflow 加「按需释放磁盘」步骤（先测 need/free，不足再删预装工具链，可释放 10–40 GB），预检公式按真实峰值收紧；macOS/full 判定为托管 runner 不可承载，full 两档改由本机 `--use-local-models` 构建后 `gh release upload`（本机模型齐全、磁盘充足），CI 只跑 mini/standard 三档。
- [HF 直连限流或网络抖动导致长构建失败] → hf_download 已有分块断点与重试；workflow 支持整 job 重跑；下载量在 tag 发布时约 50 GB，属一次性成本。
- [私仓 macOS 分钟 10× 计费，full 档下载+打包可能 30–60 分钟] → 不挂 push 触发；日常用 dispatch 单档；workflow 头注释显性提示成本。
- [分卷数量多（full 档 macOS ≈ 14 卷）影响收件人体验] → 使用说明给出复制即用的合并命令 + 校验命令；档位设计本身保证多数用户只需 4.5–7.4 GB 档（3–4 卷）。
- [档位定义在构建与冒烟两处漂移] → TIERS 单一定义于 `build_model_bundle.py`，冒烟 import 复用。

## Migration Plan

无数据迁移。规格层面 `one-click-packaging` 的「大包不走 Release」条款随本变更归档后更新；旧 `oneclick.yml` 与 slim 滚动发布行为不变。新 workflow 上线顺序：先 dispatch 单档验证（建议 `win-x64/standard`，成本最低），再 tag 全量。

## Open Questions

- `tools/bootstrap.py` 首启流程对「模型已就位」的跳过逻辑是否已完备（包内已有完整 core 时是否仍会触发下载）——实施时核实；若缺失，按「检测到必需文件完整即跳过下载」补齐，不改变规格行为。
