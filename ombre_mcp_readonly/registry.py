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
    "ombre_roadmap_read": roadmap_read,
    "ombre_handoff_window_read": handoff_window_read,
    "ombre_handoff_pr2_read": handoff_pr2_read,
    "ombre_reference_list": reference_list,
    "ombre_reference_read": reference_read,
    "ombre_intake_index_read": intake_index_read,
    "ombre_intake_batch_list": intake_batch_list,
    "ombre_intake_batch_read": intake_batch_read,
    "ombre_docs_index_read": docs_index_read,
    "ombre_status_read": status_read,
    "ombre_boundary_read": boundary_read,
}
