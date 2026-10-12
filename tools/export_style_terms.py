#!/usr/bin/env python3
"""Generate docs/style-terms.md — the bundled Chinese style-term glossary.

Source of truth: src/yue2/data/zh_style_terms.json (the offline dictionary used
by yue2.style_localization.DictionaryProvider). Terms are grouped by category;
synonyms sharing one English tag are merged inside a group and listed again in
the trailing synonym section. Unmapped terms fall back to a trailing 「其他」
section and are reported on stdout, so new dictionary entries are never lost.

    python tools/export_style_terms.py          # (re)write docs/style-terms.md
    python tools/export_style_terms.py --check  # exit 1 when the file is stale
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TERMS_FILE = ROOT / "src" / "yue2" / "data" / "zh_style_terms.json"
OUT_FILE = ROOT / "docs" / "style-terms.md"

GROUPS: list[tuple[str, tuple[str, ...]]] = [
    ("乐器与音色", (
        "三角钢琴", "中提琴", "二胡", "低音提琴", "单簧管", "双簧管", "口琴",
        "古典吉他", "古琴", "古筝", "唢呐", "圆号", "大提琴", "小号", "小提琴",
        "尤克里里", "弦乐", "弦乐四重奏", "手风琴", "打击乐", "扬琴", "木吉他",
        "木管", "架子鼓", "吉他", "班卓琴", "琵琶", "电吉他", "电贝斯", "电钢琴",
        "竖琴", "竹笛", "笛子", "管风琴", "萨克斯", "贝斯", "钢琴", "铜管",
        "键盘", "长号", "长笛", "鼓", "鼓机", "合成器", "温暖钢琴",
        "箫", "洞箫", "笙", "阮", "三弦", "柳琴", "马头琴", "埙", "陶笛",
        "锣", "尺八", "大号", "木琴", "马林巴", "钟琴", "竖笛", "铃鼓",
        "定音鼓", "手鼓",
    )),
    ("曲风流派", (
        "世界音乐", "中国风", "乡村", "低保真", "儿歌", "出神", "动漫歌曲",
        "古典", "古典音乐", "古风", "合成器流行", "合成器浪潮", "后摇", "嘻哈",
        "回响贝斯", "国风", "国风电子", "城市流行", "巴萨诺瓦", "戏曲", "拉丁",
        "摇摆", "摇滚", "放克", "新世纪", "日文流行", "日系动漫", "朋克",
        "梦幻流行", "歌剧", "死亡金属", "民乐", "民谣", "民谣摇滚", "氛围",
        "氛围音乐", "流行", "流行电子", "流行音乐", "浩室", "游戏音乐", "灵魂乐",
        "爵士", "独立", "独立摇滚", "独立流行", "环境音乐", "电子", "电子舞曲",
        "电影配乐", "福音", "节奏蓝调", "蒸汽波", "蓝调", "说唱", "迪斯科",
        "配乐", "重金属", "金属", "陷阱音乐", "雷鬼", "音乐剧", "鼓打贝斯",
        "交响乐", "管弦乐", "科技舞曲", "迷幻", "迷幻摇滚", "硬摇滚", "硬核",
        "碎拍", "融合爵士", "蓝草", "回响", "未来贝斯", "电音", "弗拉门戈",
        "探戈", "华尔兹", "进行曲", "室内乐", "后朋克", "新古典", "京剧",
        "巴洛克",
    )),
    ("语言", (
        "中文", "华语", "国语", "普通话", "粤语", "台语", "日文", "日语",
        "韩文", "韩语", "英文", "英语", "法语", "西班牙语",
        "俄语", "德语", "意大利语", "葡萄牙语", "阿拉伯语", "泰语", "越南语",
        "广东话", "闽南语",
    )),
    ("人声", (
        "人声", "伴唱", "假声", "合唱", "合唱团", "吟唱", "和声", "嘶吼", "器乐",
        "女声", "对唱", "念白", "无人声", "无伴奏合唱", "气声", "独唱", "男声",
        "童声", "纯音乐", "耳语", "阿卡贝拉",
    )),
    ("情绪与氛围", (
        "俏皮", "冰冷", "可爱", "史诗", "唯美", "壮丽", "大气", "孤独", "宁静",
        "宏伟", "平静", "庄严", "忧郁", "快乐", "怀旧", "悬疑", "悲伤", "慵懒",
        "放松", "明亮", "未来感", "柔和", "梦幻", "欢快", "治愈", "活力", "活泼",
        "浪漫", "深情", "清新", "温暖", "温柔", "激情", "激昂", "激烈", "炽热",
        "烟雨江南", "甜美", "神秘", "空灵", "紧张", "舒缓", "轻快", "青春",
        "黑暗", "复古", "夜晚", "霓虹",
        "伤感", "兴奋", "澎湃", "惆怅", "惬意", "神圣", "诡异", "幽默", "轻松",
        "失恋", "优雅", "阳光", "忧伤",
    )),
    ("速度 / 节拍 / 调性", (
        "中板", "中速", "五声音阶", "反拍", "大调", "小调", "律动", "快板",
        "快节奏", "快速", "急速", "慢板", "慢节奏", "慢速", "缓慢", "重拍",
    )),
    ("类型 / 场景 / 制作", (
        "不插电", "原声", "情歌", "抒情", "抒情慢板", "摇篮曲", "现代", "现场",
        "电影感", "钢琴曲", "阅读背景",
        "混响", "失真", "空间感", "极简", "80年代", "90年代", "黑胶", "独奏",
        "合奏", "清唱",
    )),
    ("国风与意境", (
        "禅意", "水墨", "江湖", "武侠", "仙侠", "敦煌", "国潮",
    )),
]


def load_terms(path=TERMS_FILE) -> dict[str, str]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def group_index() -> dict[str, str]:
    index: dict[str, str] = {}
    for title, keys in GROUPS:
        for key in keys:
            if key in index:
                raise ValueError(f"category table lists {key} twice")
            index[key] = title
    return index


def stale_groups(terms: dict[str, str]) -> list[str]:
    """Category-table entries that no longer exist in the dictionary."""
    return [key for _title, keys in GROUPS for key in keys if key not in terms]


def uncategorized(terms: dict[str, str]) -> list[str]:
    index = group_index()
    return [key for key in terms if key not in index]


def _entries(keys, terms: dict[str, str]) -> list[tuple[str, str]]:
    """Merge keys sharing one English tag; both sides in sorted order."""
    by_value: dict[str, list[str]] = {}
    for key in sorted(keys):
        by_value.setdefault(terms[key], []).append(key)
    merged: list[tuple[str, str]] = []
    seen: set[str] = set()
    for key in sorted(keys):
        value = terms[key]
        if value in seen:
            continue
        seen.add(value)
        merged.append((" / ".join(by_value[value]), value))
    return merged


def _table(entries: list[tuple[str, str]]) -> list[str]:
    lines = ["| 中文 | 英文 | 中文 | 英文 |", "|---|---|---|---|"]
    for i in range(0, len(entries), 2):
        left = entries[i]
        right = entries[i + 1] if i + 1 < len(entries) else ("", "")
        lines.append(f"| {left[0]} | {left[1]} | {right[0]} | {right[1]} |")
    return lines


def render(terms: dict[str, str]) -> str:
    unknown = uncategorized(terms)
    distinct = len(set(terms.values()))
    lines = [
        "# YuE2 中文风格词表",
        "",
        "> 本文件由 `python tools/export_style_terms.py` 自动生成，请勿手改；",
        "> 源数据：`src/yue2/data/zh_style_terms.json`（内置离线翻译词典）。",
        "> 创作面板「风格」中的这些中文词会按「最长匹配、逗号分词」替换为对应英文标签；",
        "> 未收录的中文词原样保留；配置了 LLM 翻译端点时优先由 LLM 翻译。",
        "",
        f"共 **{len(terms)}** 条词条，对应 **{distinct}** 个英文标签。",
        "",
    ]
    for title, keys in GROUPS:
        lines.append(f"## {title}（{len(keys)}）")
        lines.append("")
        lines.extend(_table(_entries(keys, terms)))
        lines.append("")
    if unknown:
        lines.append(f"## 其他（{len(unknown)}）")
        lines.append("")
        lines.extend(_table(_entries(unknown, terms)))
        lines.append("")
    shared: dict[str, list[str]] = {}
    for key, value in terms.items():
        shared.setdefault(value, []).append(key)
    shared = {value: sorted(keys) for value, keys in shared.items() if len(keys) > 1}
    if shared:
        lines.append("## 同义词")
        lines.append("")
        lines.append("下列多组中文词会译为同一个英文标签：")
        lines.append("")
        for value, keys in sorted(shared.items(), key=lambda item: item[0].lower()):
            lines.append(f"- `{value}` ← {'、'.join(keys)}")
        lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Generate docs/style-terms.md")
    parser.add_argument("--check", action="store_true",
                        help="exit 1 when docs/style-terms.md is out of date")
    args = parser.parse_args(argv)
    terms = load_terms()
    stale = stale_groups(terms)
    if stale:
        print(f"category table entries missing from the dictionary: {stale}",
              file=sys.stderr)
        return 2
    generated = render(terms)
    rel = OUT_FILE.relative_to(ROOT)
    if args.check:
        current = OUT_FILE.read_text(encoding="utf-8") if OUT_FILE.exists() else ""
        if current == generated:
            print(f"{rel} is in sync ({len(terms)} terms)")
            if uncategorized(terms):
                print(f"warning: uncategorized terms: {uncategorized(terms)}",
                      file=sys.stderr)
            return 0
        print(f"{rel} is stale — run: python tools/export_style_terms.py",
              file=sys.stderr)
        return 1
    OUT_FILE.write_text(generated, encoding="utf-8")
    print(f"wrote {rel} ({len(terms)} terms)")
    if uncategorized(terms):
        print(f"warning: uncategorized terms kept under 「其他」: {uncategorized(terms)}",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
