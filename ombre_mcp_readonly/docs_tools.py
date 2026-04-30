"""Pure readonly helper functions for Level 0 OmbreBrain docs access."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .allowlist import (
    DOCS_INDEX_DOC,
    INTAKE_BATCH_DOCS,
    MCP_IMPLEMENTATION_PLAN_DOC,
    PR2_HANDOFF_DOC,
    PR2_REVIEW_NOTE_DOC,
    REFERENCE_DOCS,
    REPO_ROOT,
    SINGLE_DOC_TOOL_PATHS,
    STATUS_SOURCE_PATH,
)
from .path_guard import ensure_allowed_path, ensure_safe_id


def _ok(tool: str, source_path: Path | str, content: str) -> dict:
    return {
        "status": "ok",
        "tool": tool,
        "source_path": str(source_path),
        "content": content,
        "read_only": True,
    }


def _error(tool: str, code: str, message: str, source_path: Path | str = "") -> dict:
    return {
        "status": "error",
        "tool": tool,
        "code": code,
        "message": message,
        "source_path": str(source_path),
        "read_only": True,
    }


def _read_allowed_file(tool: str, source_path: Path) -> dict:
    try:
        safe_path = ensure_allowed_path(source_path)
    except PermissionError:
        return _error(tool, "not_allowed", "Path is not allowed.", source_path)
    if not safe_path.exists():
        return _error(tool, "not_found", "Requested file does not exist.", safe_path)
    return _ok(tool, safe_path, safe_path.read_text(encoding="utf-8"))


def roadmap_read() -> dict:
    return _read_allowed_file("roadmap_read", SINGLE_DOC_TOOL_PATHS["roadmap_read"])


def handoff_window_read() -> dict:
    return _read_allowed_file("handoff_window_read", SINGLE_DOC_TOOL_PATHS["handoff_window_read"])


def handoff_pr2_read(which: str = "both") -> dict:
    tool = "handoff_pr2_read"
    try:
        choice = ensure_safe_id(which)
    except ValueError:
        return _error(tool, "invalid_id", "Missing handoff selector.")
    except PermissionError:
        return _error(tool, "not_allowed", "Selector is not allowed.")

    mapping = {
        "handoff": PR2_HANDOFF_DOC,
        "review_note": PR2_REVIEW_NOTE_DOC,
    }
    if choice == "both":
        parts = []
        for label, path in mapping.items():
            result = _read_allowed_file(tool, path)
            if result["status"] != "ok":
                return result
            parts.append(f"## {label}\n\n{result['content']}")
        return _ok(tool, f"{PR2_HANDOFF_DOC} ; {PR2_REVIEW_NOTE_DOC}", "\n\n".join(parts))
    if choice not in mapping:
        return _error(tool, "invalid_id", "Unknown PR2 handoff selector.")
    return _read_allowed_file(tool, mapping[choice])


def reference_list() -> dict:
    lines = [f"{ref_id}\t{path.name}" for ref_id, path in sorted(REFERENCE_DOCS.items())]
    return _ok("reference_list", DOCS_INDEX_DOC, "\n".join(lines))


def reference_read(ref_id: str) -> dict:
    tool = "reference_read"
    try:
        safe_id = ensure_safe_id(ref_id)
    except ValueError:
        return _error(tool, "invalid_id", "Missing reference id.")
    except PermissionError:
        return _error(tool, "not_allowed", "Reference id is not allowed.")
    path = REFERENCE_DOCS.get(safe_id)
    if path is None:
        return _error(tool, "invalid_id", "Unknown reference id.")
    return _read_allowed_file(tool, path)


def intake_index_read() -> dict:
    return _read_allowed_file("intake_index_read", SINGLE_DOC_TOOL_PATHS["intake_index_read"])


def intake_batch_list() -> dict:
    lines = [f"{batch_id}\t{path.name}" for batch_id, path in sorted(INTAKE_BATCH_DOCS.items())]
    return _ok("intake_batch_list", DOCS_INDEX_DOC, "\n".join(lines))


def intake_batch_read(batch_id: str) -> dict:
    tool = "intake_batch_read"
    try:
        safe_id = ensure_safe_id(batch_id)
    except ValueError:
        return _error(tool, "invalid_id", "Missing intake batch id.")
    except PermissionError:
        return _error(tool, "not_allowed", "Intake batch id is not allowed.")
    path = INTAKE_BATCH_DOCS.get(safe_id)
    if path is None:
        return _error(tool, "invalid_id", "Unknown intake batch id.")
    return _read_allowed_file(tool, path)


def docs_index_read() -> dict:
    return _read_allowed_file("docs_index_read", SINGLE_DOC_TOOL_PATHS["docs_index_read"])


def status_read() -> dict:
    tool = "status_read"
    try:
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--short"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.rstrip()
    except subprocess.CalledProcessError as exc:
        return _error(tool, "not_found", f"Git status read failed: {exc}", STATUS_SOURCE_PATH)
    content = f"branch: {branch}\nstatus:\n{status}" if status else f"branch: {branch}\nstatus:\n(clean)"
    return _ok(tool, STATUS_SOURCE_PATH, content)


def boundary_read() -> dict:
    tool = "boundary_read"
    preflight = _read_allowed_file(tool, SINGLE_DOC_TOOL_PATHS["boundary_read"])
    if preflight["status"] != "ok":
        return preflight
    plan = _read_allowed_file(tool, MCP_IMPLEMENTATION_PLAN_DOC)
    if plan["status"] != "ok":
        return plan
    content = (
        f"## preflight\n\n{preflight['content']}\n\n"
        f"## implementation_plan\n\n{plan['content']}"
    )
    return _ok(tool, f"{SINGLE_DOC_TOOL_PATHS['boundary_read']} ; {MCP_IMPLEMENTATION_PLAN_DOC}", content)
