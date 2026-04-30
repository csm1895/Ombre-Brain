"""Hardcoded allowlist for Level 0 readonly doc access."""

from pathlib import Path

DOCS_ROOT = Path("/Users/yangyang/Desktop/海马体/_docs")
REPO_ROOT = Path("/Users/yangyang/Desktop/海马体/Ombre-Brain")

ROADMAP_DOC = DOCS_ROOT / "OmbreBrain_usage_roadmap_v01.md"
WINDOW_HANDOFF_DOC = DOCS_ROOT / "OmbreBrain_window_continuity_handoff_v01.md"
PR2_HANDOFF_DOC = DOCS_ROOT / "OmbreBrain_nightly_job_v01_readonly_PR2_HANDOFF.md"
PR2_REVIEW_NOTE_DOC = DOCS_ROOT / "OmbreBrain_PR2_REVIEW_NOTE.md"
DOCS_INDEX_DOC = DOCS_ROOT / "OmbreBrain_DOCS_INDEX.md"
MCP_PREFLIGHT_DOC = DOCS_ROOT / "OmbreBrain_mcp_level0_readonly_preflight_v01.md"
MCP_IMPLEMENTATION_PLAN_DOC = (
    DOCS_ROOT / "OmbreBrain_mcp_level0_readonly_implementation_plan_v01.md"
)
INTAKE_README_DOC = DOCS_ROOT / "_intake" / "README_USER_MATERIAL_INTAKE.md"

REFERENCE_DOCS = {
    "memory_writing_template_v01": DOCS_ROOT / "OmbreBrain_memory_writing_template_v01_REFERENCE.md",
    "recall_ai_reference_v02": DOCS_ROOT / "OmbreBrain_recall_ai_reference_v02.md",
    "living_room_sensory_xiaowo_reference_v01": DOCS_ROOT
    / "OmbreBrain_living_room_sensory_xiaowo_reference_v01.md",
    "presence_gift_sentinel_boundary_reference_v01": DOCS_ROOT
    / "OmbreBrain_presence_gift_sentinel_boundary_reference_v01.md",
}

INTAKE_BATCH_DOCS = {
    "external_materials_batch1": DOCS_ROOT
    / "_intake"
    / "OmbreBrain_intake_2026-04-27_external_materials_BATCH1.md",
    "recall_ai_memory_template_batch2": DOCS_ROOT
    / "_intake"
    / "OmbreBrain_intake_2026-04-27_recall_ai_memory_template_BATCH2.md",
}

SINGLE_DOC_TOOL_PATHS = {
    "roadmap_read": ROADMAP_DOC,
    "handoff_window_read": WINDOW_HANDOFF_DOC,
    "docs_index_read": DOCS_INDEX_DOC,
    "intake_index_read": INTAKE_README_DOC,
    "boundary_read": MCP_PREFLIGHT_DOC,
}

STATUS_SOURCE_PATH = REPO_ROOT

ALL_ALLOWED_PATHS = frozenset(
    {
        ROADMAP_DOC,
        WINDOW_HANDOFF_DOC,
        PR2_HANDOFF_DOC,
        PR2_REVIEW_NOTE_DOC,
        DOCS_INDEX_DOC,
        MCP_PREFLIGHT_DOC,
        MCP_IMPLEMENTATION_PLAN_DOC,
        INTAKE_README_DOC,
    }
    | set(REFERENCE_DOCS.values())
    | set(INTAKE_BATCH_DOCS.values())
)
