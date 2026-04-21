#!/usr/bin/env python3
"""
OmbreBrain nightly_job v0.1 readonly draft.

只读演练：
- 读取当天新增 buckets
- 读取 notes
- 生成本地 markdown 草稿
- 不写主脑
- 不修改 bucket
- 不调用 hold/grow/trace
"""

from __future__ import annotations

import argparse
import json
import os
import re
import uuid
import traceback
from datetime import datetime, date
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def today_str() -> str:
    return date.today().isoformat()


def date_in_range(value: str, since: str, until: str) -> bool:
    """Return True if ISO datetime/date string is inside [since, until]."""
    if not value:
        return False
    day = value[:10]
    if since and day < since:
        return False
    if until and day > until:
        return False
    return True


def strip_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text

    raw_meta = parts[1]
    body = parts[2].strip()

    meta: dict[str, Any] = {}
    current_key = None

    for line in raw_meta.splitlines():
        if not line.strip():
            continue

        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*:", line):
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            meta[key] = value
            current_key = key
        elif line.strip().startswith("- ") and current_key:
            meta.setdefault(current_key, [])
            if not isinstance(meta[current_key], list):
                meta[current_key] = [meta[current_key]]
            meta[current_key].append(line.strip()[2:].strip())

    return meta, body


def load_buckets(root: Path, since: str, until: str) -> list[dict[str, Any]]:
    buckets: list[dict[str, Any]] = []

    if not root.exists():
        return buckets

    for path in root.rglob("*.md"):
        if "_nightly_logs" in path.parts:
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue

        meta, body = strip_frontmatter(text)
        created = str(meta.get("created", ""))

        if not date_in_range(created, since, until):
            continue

        buckets.append(
            {
                "path": str(path),
                "id": meta.get("id", path.stem),
                "name": meta.get("name", path.stem),
                "type": meta.get("type", ""),
                "importance": meta.get("importance", ""),
                "created": created,
                "last_active": meta.get("last_active", ""),
                "domain": meta.get("domain", ""),
                "tags": meta.get("tags", []),
                "body_preview": body[:300].replace("\n", " "),
            }
        )

    return buckets


def load_notes(root: Path, since: str, until: str) -> list[dict[str, Any]]:
    notes_file = root / "_notes" / "notes.jsonl"
    if not notes_file.exists():
        return []

    notes: list[dict[str, Any]] = []
    for line in notes_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue

        created = str(item.get("created", ""))
        if not date_in_range(created, since, until):
            continue

        notes.append(item)

    return notes


def render_note_preview(target_date: str, since: str, until: str, buckets: list[dict[str, Any]], notes: list[dict[str, Any]], out_path: Path) -> str:
    """Render a short note-style preview. This does not send anything."""
    lines: list[str] = []
    lines.append(f"【nightly_job v0.1 只读草稿｜{target_date}】")
    lines.append("")
    lines.append(f"范围：{since} 至 {until}")
    lines.append(f"读取：记忆桶 {len(buckets)} 条，便利贴 {len(notes)} 条")
    lines.append("")
    lines.append("今日小传草稿：")
    if not buckets and not notes:
        lines.append("今天没有读取到新的本地记忆碎片。")
    else:
        lines.append("今天读取到新的本地材料，已生成只读草稿，等待人工确认。")
    lines.append("")
    lines.append("需要确认：")
    lines.append("- 是否需要接 DeepSeek 生成更自然的小传")
    lines.append("- 是否有内容值得写入长期记忆")
    lines.append("- 是否有未完成事项需要更新")
    lines.append("")
    lines.append(f"草稿文件：{out_path}")
    lines.append("")
    lines.append("以上为只读草稿，未写入主脑，未发送便利贴。")
    return "\n".join(lines)


def write_error_log(out_dir: Path, run_id: str, err: BaseException) -> Path:
    """Write failure details to _nightly_logs/errors."""
    err_dir = out_dir / "errors"
    err_dir.mkdir(parents=True, exist_ok=True)
    path = err_dir / f"nightly_error_{datetime.now().strftime('%Y-%m-%d')}_{run_id}.log"
    path.write_text(
        "\n".join(
            [
                f"run_id: {run_id}",
                f"created_at: {now_iso()}",
                f"error_type: {type(err).__name__}",
                f"error: {err}",
                "",
                traceback.format_exc(),
            ]
        ),
        encoding="utf-8",
    )
    return path


def render_markdown(
    *,
    run_id: str,
    root: Path,
    target_date: str,
    since: str,
    until: str,
    buckets: list[dict[str, Any]],
    notes: list[dict[str, Any]],
) -> str:
    lines: list[str] = []

    lines.append(f"# nightly_job v0.1 只读草稿｜{target_date}")
    lines.append("")
    lines.append(f"- run_id: `{run_id}`")
    lines.append(f"- created_at: `{now_iso()}`")
    lines.append(f"- buckets_root: `{root}`")
    lines.append(f"- since: `{since}`")
    lines.append(f"- until: `{until}`")
    lines.append("- mode: `dry_run / readonly`")
    lines.append("- 写入主脑: 否")
    lines.append("- 调用 DeepSeek: 否，当前为本地 mock 草稿")
    lines.append("")

    lines.append("## 一、今日读取概览")
    lines.append("")
    lines.append(f"- 当天新增/活跃记忆桶：{len(buckets)}")
    lines.append(f"- 当天便利贴：{len(notes)}")
    lines.append("")

    lines.append("## 二、今日小传草稿")
    lines.append("")
    if not buckets and not notes:
        lines.append("今天没有读取到新的本地记忆碎片。")
    else:
        lines.append("今天读取到以下新增材料。此处只是只读草稿，后续可接 DeepSeek 生成更自然的小传。")
    lines.append("")

    lines.append("## 三、当天记忆桶")
    lines.append("")
    if not buckets:
        lines.append("无。")
    else:
        for b in buckets:
            lines.append(f"### {b.get('name') or b.get('id')}")
            lines.append("")
            lines.append(f"- id: `{b.get('id')}`")
            lines.append(f"- type: `{b.get('type')}`")
            lines.append(f"- importance: `{b.get('importance')}`")
            lines.append(f"- created: `{b.get('created')}`")
            lines.append(f"- tags: `{', '.join(b.get('tags') or []) if isinstance(b.get('tags'), list) else b.get('tags')}`")
            lines.append("")
            lines.append("> " + str(b.get("body_preview", "")).replace("\n", " "))
            lines.append("")

    lines.append("## 四、当天便利贴")
    lines.append("")
    if not notes:
        lines.append("无。")
    else:
        for n in notes:
            lines.append(f"- `{n.get('created', '')}` {n.get('sender', '')} -> {n.get('to', '') or 'all'}：{n.get('content', '')}")

    lines.append("")
    lines.append("## 五、未完成事项变化")
    lines.append("")
    lines.append("v0.1 暂未自动判断。后续接 DeepSeek 后生成候选，不直接写入。")
    lines.append("")

    lines.append("## 六、长期记忆候选")
    lines.append("")
    lines.append("v0.1 暂未自动判断。后续只列候选，等待倩倩或叶辰一确认。")
    lines.append("")

    lines.append("## 七、需要人工确认")
    lines.append("")
    lines.append("- 当前草稿未写入主脑。")
    lines.append("- 当前草稿未修改任何长期规则。")
    lines.append("- 当前草稿未调用 hold/grow/trace。")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=os.environ.get("OMBRE_BUCKETS_DIR", "buckets"))
    parser.add_argument("--date", default=today_str(), help="Single date, kept for compatibility.")
    parser.add_argument("--since", default="", help="Start date YYYY-MM-DD. Overrides --date when provided.")
    parser.add_argument("--until", default="", help="End date YYYY-MM-DD. Overrides --date when provided.")
    parser.add_argument("--out-dir", default="_nightly_logs")
    parser.add_argument("--note-preview", action="store_true", help="Also write a note-style preview file. Does not send.")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    since = args.since or args.date
    until = args.until or args.date
    run_id = uuid.uuid4().hex[:12]

    try:
        if since > until:
            raise ValueError(f"Invalid date range: since {since} > until {until}")

        buckets = load_buckets(root, since, until)
        notes = load_notes(root, since, until)

        md = render_markdown(
            run_id=run_id,
            root=root,
            target_date=args.date,
            since=since,
            until=until,
            buckets=buckets,
            notes=notes,
        )

        out_path = out_dir / f"nightly_{args.date}_{run_id}.md"
        out_path.write_text(md, encoding="utf-8")

        note_path = None
        if args.note_preview:
            note_text = render_note_preview(args.date, since, until, buckets, notes, out_path)
            note_path = out_dir / f"nightly_note_preview_{args.date}_{run_id}.txt"
            note_path.write_text(note_text, encoding="utf-8")

        print(f"nightly_job v0.1 readonly OK")
        print(f"date: {args.date}")
        print(f"since: {since}")
        print(f"until: {until}")
        print(f"buckets: {len(buckets)}")
        print(f"notes: {len(notes)}")
        print(f"output: {out_path}")
        if note_path:
            print(f"note_preview: {note_path}")
    except Exception as err:
        err_path = write_error_log(out_dir, run_id, err)
        print("nightly_job v0.1 readonly FAILED")
        print(f"run_id: {run_id}")
        print(f"error_log: {err_path}")
        raise


if __name__ == "__main__":
    main()
