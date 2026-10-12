# Web UI 基线截图

本目录是 `web/static/` 前端（Suno 像素级复刻风格）的**冻结基线截图**，与 `openspec/specs/web-ui-design/spec.md` 配套使用。任何触及 `web/static/` 的改动实施完成后，应以相同条件重新截图并与本目录对照，确认除提案声明的视觉变更外无差异。

## 截图条件

- 视口：**1440 × 900**（CSS 像素，Playwright `page.screenshot({ scale: "css" })`）
- 服务：本地 `python web/server.py`（`http://127.0.0.1:7860/`）
- 语言：`en/` 与 `zh/` 各一套（在设置弹窗「界面语言」切换）
- 日期：2026-10-11

## 页面清单

| 文件 | 页面 | 到达方式 |
|---|---|---|
| `create-simple.png` | Create · 简单模式 | 侧栏「创作」，默认态 |
| `create-advanced.png` | Create · 高级模式（展开 More Options） | 点「高级」→ 点「More Options」 |
| `library.png` | Library · Songs | 侧栏「音乐库」 |
| `detail.png` | 歌曲详情页 | 列表中点一首歌（基线为 Ink Moonlight） |
| `settings.png` | 设置弹窗 | 侧栏「设置」 |
| `models.png` | 模型页 | 侧栏「模型」 |
| `llm.png` | LLM 配置页（供应商列表 + 试聊面板；页内下滚一屏以完整取景） | 侧栏「LLM 配置」 |

## 更新约定

- 只有经 OpenSpec 提案显式声明并经用户确认的「视觉变更」才允许更新对应截图；在变更的 tasks 中列出要更新的文件。
- 新增页面时，按相同视口与命名规范（kebab-case）补截，en/zh 各一张。
- 截图是**人工核查参照**，不是自动化像素门禁；动态内容（列表数据、时间、进度）差异属正常。
