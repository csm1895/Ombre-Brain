"""Readonly ombre.* tool registry.

This is intentionally just a Python mapping for now. It is not wired into the
main MCP server yet.
"""

from .docs_tools import (
    boundary_read,
    docs_index_read,
    handoff_pr2_read,
    handoff_window_read,
    intake_batch_list,
    intake_batch_read,
    intake_index_read,
    reference_list,
    reference_read,
    roadmap_read,
    status_read,
)

READONLY_TOOL_REGISTRY = {
    "ombre.roadmap.read": roadmap_read,
    "ombre.handoff.window.read": handoff_window_read,
    "ombre.handoff.pr2.read": handoff_pr2_read,
    "ombre.reference.list": reference_list,
    "ombre.reference.read": reference_read,
    "ombre.intake.index.read": intake_index_read,
    "ombre.intake.batch.list": intake_batch_list,
    "ombre.intake.batch.read": intake_batch_read,
    "ombre.docs.index.read": docs_index_read,
    "ombre.status.read": status_read,
    "ombre.boundary.read": boundary_read,
}
