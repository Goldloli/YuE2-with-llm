# Tasks: expand-style-terms

## 1. 词表数据

- [x] 1.1 修正 2 处映射：慢板→adagio；阅读背景→background music（抒情慢板保持 slow ballad）
- [x] 1.2 新增 80 条词条（乐器 19 / 流派 22 / 情绪 13 / 制作 10 / 国风 7 / 语言 9；218→298），按 Unicode 排序插入，既有行不动
- [x] 1.3 数据自检：JSON 可加载；键全部含中文、值全部为纯 ASCII 英文；无重复键；最长匹配抽查（回响贝斯→dubstep、洞箫→xiao、手鼓→hand drums、锣鼓→gong/drums）

## 2. 测试

- [x] 2.1 更新既有断言：「慢板」样例值 → adagio；规模断言 150–250 → 250–350
- [x] 2.2 新增回归样例：新增词命中（如「洞箫，笙，埙，大号，木琴」）、最长匹配（回响贝斯）、修正映射（慢板/阅读背景/抒情慢板）、语言覆盖（俄语，德语，意大利语，广东话）
- [x] 2.3 `.venv/bin/python -m pytest -q` 全绿（258 passed, 12 skipped）

## 3. 收尾

- [x] 3.1 若 `style-terms-glossary` 已实施：重新生成 `docs/style-terms.md` 并跑 `--check`（新词条自动入档）
- [x] 3.2 `openspec validate expand-style-terms --strict`；归档；`codegraph sync`
