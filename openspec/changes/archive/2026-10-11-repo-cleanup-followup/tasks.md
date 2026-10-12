# Tasks: repo-cleanup-followup

## 1. 删除一次性迭代语料

- [x] 1.1 删除 `compare/` 整个目录（66 个文件）；验证：目录不存在，`docs/ui-baseline/` 与 `ref-suno/` 完好
- [x] 1.2 删除 `outputs/bench-torch.json`；验证：`outputs/` 顶层无散落文件

## 2. 收尾清缓存

- [x] 2.1 清除全部 `__pycache__/`（收尾动作，之后不再运行测试/长命令以免再生）；验证：`find -name __pycache__` 为空

## 3. 校验与归档

- [x] 3.1 `openspec validate repo-cleanup-followup --strict`；归档（规格修订生效：保留清单去除 compare/、新增两条规则）；`codegraph sync`
- [x] 3.2 根目录与体积复核：对照保留清单（ref-suno/ docs/ models/ web/ outputs/ oneclick-packages/ …）确认零误删；`du -sh` 对比清理前后
