#!/usr/bin/env python3
"""
Build a local daily_diary draft from nightly_job readonly outputs.

Readonly:
- reads nightly JSON summary
- reads markdown draft
- writes local daily diary draft
- does not call DeepSeek
- does not write main brain
- does not send notes
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_latest_summary(logs_dir: Path, date: str) -> Path:
    files = sorted(
        logs_dir.glob(f"nightly_summary_{date}_*.json"),
        key=lambda p: p.stat().st_mtime,
    )
    if not files:
        raise FileNotFoundError(f"No nightly summary found for {date} in {logs_dir}")
    return files[-1]


def find_latest_summary_by_range(logs_dir: Path, since: str, until: str) -> Path:
    files = sorted(
        logs_dir.glob(f"nightly_summary_{until}_*.json"),
        key=lambda p: p.stat().st_mtime,
    )
    for path in reversed(files):
        try:
            data = load_json(path)
        except Exception:
            continue
        if str(data.get("since", "")) == since and str(data.get("until", "")) == until:
            return path
    if files:
        return files[-1]
    raise FileNotFoundError(f"No nightly summary found for range {since} -> {until} in {logs_dir}")


def find_latest_summary_by_range(logs_dir: Path, since: str, until: str) -> Path:
    files = sorted(
        logs_dir.glob(f"nightly_summary_{until}_*.json"),
        key=lambda p: p.stat().st_mtime,
    )
    for path in reversed(files):
        try:
            data = load_json(path)
        except Exception:
            continue
        if str(data.get("since", "")) == since and str(data.get("until", "")) == until:
            return path
    if files:
        return files[-1]
    raise FileNotFoundError(f"No nightly summary found for range {since} -> {until} in {logs_dir}")


def resolve_markdown(summary: dict[str, Any], logs_dir: Path, date: str) -> Path:
    md = summary.get("markdown_output")
    if md:
        path = Path(str(md)).expanduser()
        if path.exists():
            return path

    files = sorted(
        logs_dir.glob(f"nightly_{date}_*.md"),
        key=lambda p: p.stat().st_mtime,
    )
    if not files:
        raise FileNotFoundError(f"No nightly markdown draft found for {date} in {logs_dir}")
    return files[-1]


def get_counts(summary: dict[str, Any]) -> dict[str, Any]:
    counts = summary.get("counts")
    return counts if isinstance(counts, dict) else {}


def render_diary_draft(
    *,
    date_label: str,
    run_id: str,
    summary: dict[str, Any],
    markdown_path: Path,
) -> str:
    counts = get_counts(summary)
    bucket_count = counts.get("buckets", 0)
    note_count = counts.get("notes", 0)
    by_type = counts.get("buckets_by_type", {})
    by_importance = counts.get("buckets_by_importance", {})
    high_ids = summary.get("high_importance_bucket_ids", [])

    lines: list[str] = []

    lines.append(f"# daily_diary v0.2 只读草稿｜{date_label}")
    lines.append("")
    lines.append(f"- run_id: `{run_id}`")
    lines.append(f"- 来源草稿: `{markdown_path}`")
    lines.append("- 写入主脑: 否")
    lines.append("- 调用 DeepSeek: 否")
    lines.append("- 发送便利贴: 否")
    lines.append("- 状态: 本地只读草稿，等待人工确认")
    lines.append("")

    lines.append("## 一、今日素材概览")
    lines.append("")
    lines.append(f"- 读取记忆桶：{bucket_count}")
    lines.append(f"- 读取便利贴：{note_count}")

    if by_type:
        lines.append("- 类型统计：")
        for k, v in by_type.items():
            lines.append(f"  - {k}: {v}")

    if by_importance:
        lines.append("- 重要度统计：")
        for k, v in by_importance.items():
            lines.append(f"  - {k}: {v}")

    if high_ids:
        lines.append("- 高重要度候选：")
        for item in high_ids:
            lines.append(f"  - `{item}`")
    lines.append("")

    lines.append("## 二、今日小传草稿")
    lines.append("")
    lines.append(
        "今天读取到一批本地海马体材料，并生成了只读整理草稿。"
        "当前版本暂不自动写入主脑，也不调用 DeepSeek，只把可能需要人工确认的内容先整理出来。"
    )
    lines.append("")
    lines.append(
        "如果后续接入 DeepSeek，本段可由模型根据 nightly markdown 草稿改写成更自然的日记；"
        "但在 v0.2 骨架阶段，只保留安全、克制、可复核的本地草稿。"
    )
    lines.append("")

    lines.append("## 三、可回响线索候选")
    lines.append("")
    lines.append("v0.2 骨架暂不自动判断。后续可从以下维度提取：")
    lines.append("")
    lines.append("- 地点")
    lines.append("- 人物")
    lines.append("- 事件")
    lines.append("- 物件")
    lines.append("- 情绪")
    lines.append("- 项目状态")
    lines.append("- 未完成事项")
    lines.append("")

    lines.append("## 四、适合淡化的内容")
    lines.append("")
    lines.append("v0.2 骨架暂不自动判断。原则上以下内容适合后续淡化：")
    lines.append("")
    lines.append("- 一次性测试输出")
    lines.append("- 重复命令回显")
    lines.append("- 临时报错")
    lines.append("- 普通吃喝流水")
    lines.append("- 无后续意义的短期状态")
    lines.append("")

    lines.append("## 五、需要人工确认")
    lines.append("")
    lines.append("- 是否需要接 DeepSeek 生成更自然的日记")
    lines.append("- 是否有内容值得进入 monthly_digest")
    lines.append("- 是否有内容值得进入 echo_index")
    lines.append("- 是否有未完成事项需要更新")
    lines.append("")

    lines.append("## 六、安全声明")
    lines.append("")
    lines.append("本文件为 daily_diary v0.2 只读草稿。")
    lines.append("未写入主脑。")
    lines.append("未调用 DeepSeek。")
    lines.append("未调用 hold/grow/trace。")
    lines.append("未发送便利贴。")
    lines.append("不得作为长期记忆直接写入。")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="", help="Target date YYYY-MM-DD")
    parser.add_argument("--since", default="", help="Range start date YYYY-MM-DD")
    parser.add_argument("--until", default="", help="Range end date YYYY-MM-DD")
    parser.add_argument("--logs-dir", default="_nightly_logs")
    parser.add_argument("--summary", default="", help="Optional explicit nightly_summary json path")
    parser.add_argument("--out-dir", default="_nightly_logs")
    args = parser.parse_args()

    logs_dir = Path(args.logs_dir).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.date and (args.since or args.until):
        raise ValueError("Use either --date or --since/--until, not both.")

    if not args.date and not (args.since and args.until):
        raise ValueError("Provide --date or both --since and --until.")

    if args.since and args.until and args.since > args.until:
        raise ValueError(f"Invalid date range: since {args.since} > until {args.until}")

    if args.summary:
        summary_path = Path(args.summary).expanduser().resolve()
    elif args.date:
        summary_path = find_latest_summary(logs_dir, args.date)
    else:
        summary_path = find_latest_summary_by_range(logs_dir, args.since, args.until)

    summary = load_json(summary_path)

    date_label = args.date or f"{args.since}_to_{args.until}"
    markdown_lookup_date = args.date or args.until
    markdown_path = resolve_markdown(summary, logs_dir, markdown_lookup_date)

    run_id = str(summary.get("run_id") or summary_path.stem.split("_")[-1])

    output = render_diary_draft(
        date_label=date_label,
        run_id=run_id,
        summary=summary,
        markdown_path=markdown_path,
    )

    out_path = out_dir / f"daily_diary_draft_{date_label}_{run_id}.md"
    out_path.write_text(output, encoding="utf-8")

    print("daily diary draft build OK")
    print(f"date: {date_label}")
    print(f"summary: {summary_path}")
    print(f"markdown: {markdown_path}")
    print(f"output: {out_path}")


if __name__ == "__main__":
    main()
