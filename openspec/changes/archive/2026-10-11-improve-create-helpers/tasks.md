# Tasks: improve-create-helpers

- [x] 1.1 `web/server.py`：`/api/examples` 改返回 `{scores, lyrics}`（扫描 examples/*.json 中非空 lyrics 条目）；`web/static/app.js` attach 弹窗适配 `scores`；验证：curl 返回形状 + attach 弹窗仍可选示例谱
- [x] 1.2 `app.js` ✨：真实示例 + 硬编码兜底随机选取；非空时 confirmDialog 确认；验证：空框直填、非空弹确认、取消不变、确认替换、示例池含中文
- [x] 1.3 `app.js` 魔法棒：非空时确认后才覆盖（确认后 deck 前进与 chips 刷新）；验证：同 1.2
- [x] 1.4 牌堆：`trumpette`→`trumpet` + 追加 5 组中文建议；`zh_style_terms.json` 补 11 词条；验证：`localize_style` 对 5 组中文全量翻译无残留
- [x] 1.5 i18n：确认文案 5 条（en/zh）
- [x] 2.1 测试：`/api/examples` 形状用例；词典计数断言带内；全量 pytest 绿
- [x] 2.2 浏览器实测五场景 + 对照 create-advanced 基线确认零差异；`openspec validate improve-create-helpers --strict`；归档；`codegraph sync`
