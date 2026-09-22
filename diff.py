#!/usr/bin/env python3
"""Diff baseline.json against snapshot.json and emit drift-report.md."""

import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

SIGNAL_LABEL = {
    "eol": "EOL / 迁移",
    "field_default": "字段默认值变化",
    "sdk_version": "SDK 大版本 / pinned API",
    "api_version": "API 版本变更",
}


def load(name):
    p = os.path.join(ROOT, name)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def fingerprint(e):
    return (e.get("sha256"), e.get("etag"), e.get("last_modified"), e.get("status"))


def main():
    base = load("baseline.json")
    snap = load("snapshot.json")
    if snap is None:
        print("snapshot.json 不存在，先运行 fetch.py", file=sys.stderr)
        sys.exit(1)

    changed, new, failed, unchanged = [], [], [], 0

    for sid, cur in snap["sources"].items():
        if not cur.get("ok"):
            failed.append((sid, cur))
        elif base is None or sid not in base.get("sources", {}):
            new.append((sid, cur))
        elif fingerprint(cur) != fingerprint(base["sources"][sid]):
            changed.append((sid, base["sources"][sid], cur))
        else:
            unchanged += 1

    lines = [
        "# PSP 漂移监测报告",
        "",
        f"生成时间：{snap['generated_at']}",
        "",
        f"- 变化：{len(changed)} ｜ 新增：{len(new)} ｜ 失败：{len(failed)} ｜ 未变化：{unchanged}",
        "",
    ]

    if base is None:
        lines.append("> 本次为首次快照，已建立基线，无历史可对比。")

    if changed:
        lines.append("## 有变化的源（需判断是否为静默破坏）")
        lines.append("")
        for sid, prev, cur in changed:
            lines.append(
                f"- **{cur['platform']} / {cur['name']}**（信号：{SIGNAL_LABEL.get(cur['signal'], cur['signal'])}）"
            )
            lines.append(f"  - {cur['url']}")
            lines.append(
                f"  - 指纹变化：{prev.get('sha256','-')[:12]} → {cur.get('sha256','-')[:12]}"
            )
            if prev.get("last_modified") != cur.get("last_modified"):
                lines.append(f"  - last-modified：{prev.get('last_modified')} → {cur.get('last_modified')}")
            lines.append("")

    if new:
        lines.append("## 新增的源")
        lines.append("")
        for sid, cur in new:
            lines.append(f"- {cur['platform']} / {cur['name']} — {cur['url']}")
        lines.append("")

    if failed:
        lines.append("## 抓取失败的源（网络/反爬/改版）")
        lines.append("")
        for sid, cur in failed:
            lines.append(f"- {cur['platform']} / {cur['name']} — {cur.get('error')}")
        lines.append("")

    lines.append("## 判断与动作")
    lines.append("")
    lines.append("有变化时按三条信号判断要不要动手：")
    lines.append("1. EOL / 迁移：有截止日，但迁移窗口最容易静默失败。")
    lines.append("2. 字段默认值变化：不报错、只是突然没值。")
    lines.append("3. SDK 大版本 + pinned API：升级动作本身会掩盖风险。")
    lines.append("")
    lines.append("## 升级前回归清单")
    lines.append("")
    lines.append("- 固定 API version，升级是显式动作，不是依赖更新附带的结果")
    lines.append("- 成功、拒绝、过期、退款、拒付、重复回调各跑一遍")
    lines.append("- 字段缺失时是报错还是静默继续，要在测试里明确断言")
    lines.append("- 订阅类变更单独过：创建、续费、取消、升级")
    lines.append("- 沙盒和生产各触发一次同一事件，确认两边行为一致")

    out = os.path.join(ROOT, "drift-report.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {out}: {len(changed)} changed / {len(new)} new / {len(failed)} failed / {unchanged} unchanged")


if __name__ == "__main__":
    main()
