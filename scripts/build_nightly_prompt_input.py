#!/usr/bin/env python3
"""
Build a local DeepSeek prompt input package for nightly_job v0.1.

Readonly:
- reads prompt template
- reads nightly JSON summary
- reads markdown draft
- writes a local prompt input markdown file
- does not call DeepSeek
- does not write main brain
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_latest_summary(logs_dir: Path, date: str) -> Path:
    pattern = f"nightly_summary_{date}_*.json"
    files = sorted(logs_dir.glob(pattern), key=lambda p: p.stat().st_mtime)
    if not files:
        raise FileNotFoundError(f"No summary found: {logs_dir}/{pattern}")
    return files[-1]


def resolve_markdown(summary: dict[str, Any], fallback_logs_dir: Path, date: str) -> Path:
    md = summary.get("markdown_output")
    if md:
        path = Path(str(md)).expanduser()
        if path.exists():
            return path

    files = sorted(fallback_logs_dir.glob(f"nightly_{date}_*.md"), key=lambda p: p.stat().st_mtime)
    if not files:
        raise FileNotFoundError(f"No markdown draft found for date {date}")
    return files[-1]


def build_prompt_input(prompt_template: str, summary_text: str, markdown_text: str) -> str:
    return "\n".join(
        [
            "# nightly_job DeepSeek 输入包",
            "",
            "状态：本文件只用于人工检查或未来调用 DeepSeek。",
            "当前未调用 DeepSeek，未写主脑，未发便利贴。",
            "",
            "---",
            "",
            "## 一、Prompt 模板",
            "",
            prompt_template.strip(),
            "",
            "---",
            "",
            "## 二、JSON Summary",
            "",
            "```json",
            summary_text.strip(),
            "```",
            "",
            "---",
            "",
            "## 三、Markdown 草稿",
            "",
            markdown_text.strip(),
            "",
            "---",
            "",
            "## 四、安全声明",
            "",
            "- 本文件只是 prompt 输入包。",
            "- 未调用 DeepSeek。",
            "- 未写入主脑。",
            "- 未调用 hold/grow/trace。",
            "- 未发送便利贴。",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Target date YYYY-MM-DD")
    parser.add_argument("--logs-dir", default="_nightly_logs")
    parser.add_argument("--prompt", default="prompts/nightly_job_deepseek_v01.md")
    parser.add_argument("--summary", default="", help="Optional explicit nightly_summary json path")
    parser.add_argument("--out-dir", default="_nightly_logs")
    args = parser.parse_args()

    logs_dir = Path(args.logs_dir).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    prompt_path = Path(args.prompt).expanduser().resolve()
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt template not found: {prompt_path}")

    summary_path = Path(args.summary).expanduser().resolve() if args.summary else find_latest_summary(logs_dir, args.date)
    summary = load_json(summary_path)
    md_path = resolve_markdown(summary, logs_dir, args.date)

    run_id = str(summary.get("run_id") or summary_path.stem.split("_")[-1])

    prompt_template = prompt_path.read_text(encoding="utf-8")
    summary_text = json.dumps(summary, ensure_ascii=False, indent=2)
    markdown_text = md_path.read_text(encoding="utf-8")

    output = build_prompt_input(prompt_template, summary_text, markdown_text)

    out_path = out_dir / f"nightly_prompt_input_{args.date}_{run_id}.md"
    out_path.write_text(output, encoding="utf-8")

    print("nightly prompt input build OK")
    print(f"date: {args.date}")
    print(f"prompt: {prompt_path}")
    print(f"summary: {summary_path}")
    print(f"markdown: {md_path}")
    print(f"output: {out_path}")


if __name__ == "__main__":
    main()
