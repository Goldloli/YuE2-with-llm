# Tasks

## 1. 回滚内嵌模型包

- [x] 1.1 删除 `.github/workflows/oneclick-models.yml`、`packaging/build_model_bundle.py`、`tests/test_model_bundle.py` 与未归档变更目录 `openspec/changes/2026-10-27-oneclick-model-bundles/`；`packaging/smoke_package.py` 回退为瘦包冒烟。验证：`git status` 无残留引用，`pytest` 与 `actionlint` 通过
- [x] 1.2 `tools/bootstrap.py` 移除 `models/.bundle` 分支（`bundled_package()` 及 extras/transcribe 跳过逻辑），保留 `any_engine_ready` / `mlx_variants`；删除旧 `tests/test_bootstrap_bundle.py`，新增 `tests/test_bootstrap.py`。验证：MLX-only 目录不再拉 torch core；默认运行不下载任何模型
- [x] 1.3 `packaging/使用说明.md` 删除「内嵌模型包（免首启下载，分卷分发）」整节与 `--with-models` 相关表述。验证：全文检索无「分卷 / part-aa / 档位」残留

## 2. 移除本地大包模式

- [x] 2.1 `packaging/build_package.py` 删除 `--with-models` / `--platform`、`PLATFORMS` / `STORE_SUFFIXES` / `MODEL_EXCLUDE` / `model_dirs` / `check_models`、模型内嵌与平台命名分支；`make_zip` 只打源码。验证：`--help` 无该参数；本地构建瘦包成功
- [x] 2.2 `README.md` 一键包段落删掉大包命令，改为「瘦包 + 应用内下载 + 渠道切换」

## 3. 下载渠道解析（hf_download.py）

- [x] 3.1 新增 `--source {mirror,huggingface}` 与 `--endpoint URL`；端点解析优先级：`--endpoint` > `--source` > `YUE2_HF_ENDPOINT` > 已保存 `download_source`（读 `web/data/settings.json`）> 默认 `mirror`
- [x] 3.2 下载失败时打印当前渠道、可切换的另一渠道与切换方式（`--source` / 模型页），保留分片续传；不做自动跨渠道重试（`run()` 的 `SystemExit(1)` 改为带信息的 `RuntimeError`）
- [x] 3.3 新增 `tests/test_download_channels.py`（9 个用例：优先级矩阵、设置读取、非法值忽略、`set_endpoint`、未知模式、失败提示）。验证：通过

## 4. 首启只准备环境 + 应用内下载引导

- [x] 4.1 `tools/start.py`：`env_ready()`（`.venv` 解释器 + `.deps-installed`）不满足时跑 `bootstrap.py --yes --skip-models`，**不再下载模型**；缺模型只打印终端提示
- [x] 4.2 `web/server.py` `/api/state` 增加 `core_installed`（核心模型文件齐备）
- [x] 4.3 `web/static/app.js`：核心模型缺失时自动切到「模型」页 + toast 一次；`createSong()` 缺模型时引导到模型页；新增 `models.firstRun` / `models.coreMissing` 中英文案（无视觉变更）
- [x] 4.4 `tools/bootstrap.py`：默认只准备环境；新增 `--models`（显式下载核心模型）与 `--download-source`；交互式 `--models` 询问「1 国内 / 2 国外」并写入 `web/data/settings.json`，已保存不重复询问；`--yes` 用已保存值或默认 `mirror`
- [x] 4.5 `tests/test_bootstrap.py`（10 个用例：默认不下载、`--models`/渠道转发、`--mlx`、交互选择持久化、固定源不提问、设置合并、引擎判定、`env_ready`）+ `tests/test_web_models.py` 的 `core_installed` 断言

## 5. 文档

- [x] 5.1 `packaging/使用说明.md`：快速开始写「首启只装环境、页面停在模型页下载核心模型」；新增「下载源：国内网络 / 国外网络」小节（两渠道对照、页面切换、`--source`、默认镜像）；更新可选组件命令与 FAQ 下载失败处理
- [x] 5.2 `README.md` 一键包段落同步（瘦包 + 应用内下载 + 渠道选择 + `--source`）
- [x] 5.3 `tools/hf_download.py` 模块 docstring 写清两种渠道与优先级

## 6. 验证与收尾

- [x] 6.1 `pytest`：314 passed / 12 skipped / 1 failed（既有沙箱 pty 用例，与改动无关）；`openspec validate 2026-10-27-slim-package-download-channels --strict` 通过；`actionlint` 对现有 workflow 无新增问题
- [x] 6.2 本地构建瘦包并冒烟：`build_package.py` 产出 9.0 MiB / 175 条目的 zip，`smoke_package.py` 通过
- [x] 6.3 commit（d24cd81）+ push；`oneclick.yml` run 40491392197 双平台构建 + 发布全绿，`oneclick-latest` 资产已更新为 20261027 两份瘦包 + sha256
- [x] 6.4 删除 GitHub release `oneclick-models-latest`（含 tag，10 个试跑资产）；确认无 `models-v*` tag，`oneclick-latest` 保留
- [x] 6.5 归档本变更（`openspec archive`），把 `one-click-packaging` 规格 delta 合入主规格
