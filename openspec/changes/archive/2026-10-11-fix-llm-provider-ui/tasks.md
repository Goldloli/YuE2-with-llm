# Tasks: fix-llm-provider-ui

（用户直接下修复指令后实施并验证；按项目惯例补记变更。）

## 1. 下拉可点击性

- [x] 1.1 根因修复：`#drop-menu` 全局点外关闭白名单引入通用标记 `[data-drop-opener]`（保留旧白名单）
- [x] 1.2 标注触发器：`#lpf-preset`、`#lpf-models-pick`、`#llm-active-pick` 添加 `data-drop-opener`
- [x] 1.3 **真实点击**验证：平台预设 → 菜单保持展开并可选；当前使用 → 可展开；已拉取模型 → 可展开并回填

## 2. 供应商弹窗版式（对齐参考项目对话框）

- [x] 2.1 版式重做：标签列 92px + 控件列占满；输入框全宽（`.llm-form-field/label/control/input/select/footer`，复用既有令牌）
- [x] 2.2 「默认模型」行 = 输入框 + 「拉取模型」；拉取成功后显示「已拉取模型」下拉（openDrop；未填自动取第一个）
- [x] 2.3 「启用」改用既有 `.switch` 开关；底部「取消 / 保存」按钮行；API Key 行带「清除 Key」（编辑态）
- [x] 2.4 i18n：`llm.fetchedModels`（en/zh）
- [x] 2.5 **真实点击**全链路：预设自动填充（手改名不覆盖）→ 模拟端点拉取（3 模型）→ 已拉取模型选择 → 保存（掩码、自动当前使用）→ 编辑回填（掩码占位、开关、清除 Key）→ 删除

## 3. 收尾

- [x] 3.1 清理演示数据（删除测试供应商）；`node --check` 通过
- [x] 3.2 `openspec validate fix-llm-provider-ui --strict`；归档；`codegraph sync`
