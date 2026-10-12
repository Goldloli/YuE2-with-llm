# Tasks: freeze-web-ui-design

## 1. 规则落地

- [x] 1.1 `AGENTS.md` 新增「前端风格冻结」一节：指向 `openspec/specs/web-ui-design`，规定触及 `web/static/` 的提案必须自查该规格、视觉变更必须显式声明并经用户确认；验证：AGENTS.md 内容与 spec 表述一致
- [x] 1.2 在本变更归档前，确认 `support-chinese-style-prompts` 提案已注明遵守本基线（嗓音后缀改动为行为修复、零视觉差异）；验证：该提案 proposal.md 中有对应说明

## 2. 基线截图

- [x] 2.1 启动 web 服务，用 Playwright 以 1440×900 视口截取基线：Create 简单模式、Create 高级模式（展开 More Options）、Library、歌曲详情页、设置弹窗，en 与 zh 各一套，存入 `docs/ui-baseline/{en,zh}/`；验证：目录内 10 张截图齐全且无渲染错误
- [x] 2.2 在 `docs/ui-baseline/README.md` 写明截图视口、页面清单与更新约定；验证：后续改动者可按 README 复现截图

## 3. 校验与归档

- [x] 3.1 `openspec validate freeze-web-ui-design --strict` 通过；验证：命令输出无 error
- [x] 3.2 走 openspec-archive-change 流程归档，确认 `openspec/specs/web-ui-design/spec.md` 生成且 Purpose 已填入；验证：`openspec list` 中该变更已归档、spec 内容完整
