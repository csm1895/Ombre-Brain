from starlette.responses import Response
# ============================================================
# Module: MCP Server Entry Point (server.py)
# 模块：MCP 服务器主入口
#
# Starts the Ombre Brain MCP service and registers memory
# operation tools for Claude to call.
# 启动 Ombre Brain MCP 服务，注册记忆操作工具供 Claude 调用。
#
# Core responsibilities:
# 核心职责：
#   - Initialize config, bucket manager, dehydrator, decay engine
#     初始化配置、记忆桶管理器、脱水器、衰减引擎
#   - Expose 5 MCP tools:
#     暴露 5 个 MCP 工具：
#       breath — Surface unresolved memories or search by keyword
#                浮现未解决记忆 或 按关键词检索
#       hold   — Store a single memory
#                存储单条记忆
#       grow   — Diary digest, auto-split into multiple buckets
#                日记归档，自动拆分多桶
#       trace  — Modify metadata / resolved / delete
#                修改元数据 / resolved 标记 / 删除
#       pulse  — System status + bucket listing
#                系统状态 + 所有桶列表
#
# Startup:
# 启动方式：
#   Local:  python server.py
#   Remote: OMBRE_TRANSPORT=streamable-http python server.py
#   Docker: docker-compose up
# ============================================================

import os
import sys
import json
import random
import logging
import asyncio
import time
import shutil
from difflib import SequenceMatcher
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
import httpx
import anthropic

# --- Ensure same-directory modules can be imported ---
# --- 确保同目录下的模块能被正确导入 ---
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP

from bucket_manager import BucketManager
from dehydrator import Dehydrator
from decay_engine import DecayEngine
from utils import load_config, setup_logging, clock_now

try:
    from ombre_mcp_readonly.registry import READONLY_TOOL_REGISTRY
except ModuleNotFoundError as e:
    READONLY_TOOL_REGISTRY = {}
    logging.getLogger("ombre_brain").warning(
        f"Optional ombre_mcp_readonly package is unavailable; readonly tools disabled: {e}"
    )

# --- Load config & init logging / 加载配置 & 初始化日志 ---
config = load_config()
setup_logging(config.get("log_level", "INFO"))
logger = logging.getLogger("ombre_brain")

# --- Initialize three core components / 初始化三大核心组件 ---
bucket_mgr = BucketManager(config)                  # Bucket manager / 记忆桶管理器
dehydrator = Dehydrator(config)                      # Dehydrator / 脱水器
decay_engine = DecayEngine(config, bucket_mgr)       # Decay engine / 衰减引擎

# --- Create MCP server instance / 创建 MCP 服务器实例 ---
# host="0.0.0.0" so Docker container's SSE is externally reachable
# stdio mode ignores host (no network)
mcp = FastMCP(
    "Ombre Brain",
    host="0.0.0.0",
    port=int(os.environ.get("PORT", 8000)),
)

# --- Sticky notes directory (used by both HTTP API and MCP tools) ---
# --- 便利贴目录（HTTP API 和 MCP 工具共用）---
NOTES_DIR = os.path.join(config.get("buckets_dir", os.path.join(os.path.dirname(os.path.abspath(__file__)), "buckets")), "notes")
os.makedirs(NOTES_DIR, exist_ok=True)


def _runtime_storage_base() -> str:
    bucket_base = (
        os.environ.get("OMBRE_BUCKETS_DIR")
        or config.get("buckets_dir")
        or os.path.join(os.path.dirname(os.path.abspath(__file__)), "buckets")
    )
    return os.environ.get("OMBRE_RUNTIME_DIR", os.path.join(bucket_base, "_runtime"))

# --- CC online status tracking / CC 在线状态追踪 ---
# CC heartbeats every 2 min; if no heartbeat for 5 min, considered offline
CC_HEARTBEAT_TIMEOUT = int(os.environ.get("CC_HEARTBEAT_TIMEOUT", "300"))
_cc_last_heartbeat = 0.0  # epoch timestamp of last heartbeat

def _cc_is_online() -> bool:
    import time
    return (time.time() - _cc_last_heartbeat) < CC_HEARTBEAT_TIMEOUT

# --- Task push queue for SSE streaming / 任务推送队列 ---
_task_subscribers: list[asyncio.Queue] = []

# --- Runtime readiness for fresh-window first hop / 新窗口第一跳运行时就绪状态 ---
_runtime_boot_ts = time.time()
_runtime_ready = False
_runtime_ready_last_ok = 0.0
_runtime_ready_last_error = ""

RUNTIME_FEATURES = {
    "runtime_features_http_endpoint": True,
    "runtime_features_mcp_tool": True,
    "runtime_tool_manifest_http_endpoint": True,
    "runtime_tool_manifest_mcp_tool": True,
    "runtime_schema_expectations_http_endpoint": True,
    "runtime_schema_expectations_mcp_tool": True,
    "runtime_diagnostics_http_endpoint": True,
    "runtime_diagnostics_mcp_tool": True,
    "runtime_connector_check_http_endpoint": True,
    "runtime_connector_check_mcp_tool": True,
    "associated_memory_after_writes": True,
    "associated_memory_shows_provenance": True,
    "hold_provenance_defaults": True,
    "grow_provenance_defaults": True,
    "bucket_metadata_provenance_persistence": True,
    "diary_review_duplicate_metadata_persistence": True,
    "cadence_draft_runtime_persistence": True,
    "diary_review_duplicate_detection": True,
}
RUNTIME_FEATURES_VERSION = "2026-05-05.provenance-v1"
RUNTIME_FEATURE_COMMITS = {
    "runtime_features_http_endpoint": "a4528ec",
    "runtime_features_mcp_tool": "self",
    "runtime_tool_manifest_http_endpoint": "self",
    "runtime_tool_manifest_mcp_tool": "self",
    "runtime_schema_expectations_http_endpoint": "self",
    "runtime_schema_expectations_mcp_tool": "self",
    "runtime_diagnostics_http_endpoint": "self",
    "runtime_diagnostics_mcp_tool": "self",
    "runtime_connector_check_http_endpoint": "self",
    "runtime_connector_check_mcp_tool": "self",
    "associated_memory_after_writes": "4d93255",
    "hold_provenance_defaults": "926b92d",
    "associated_memory_shows_provenance": "c4448c8",
    "grow_provenance_defaults": "7c32ed6",
    "bucket_metadata_provenance_persistence": "c662017",
}
RUNTIME_EXPECTED_MCP_TOOLS = [
    "accept_diary_review",
    "breath",
    "check_logs",
    "dream",
    "dream_fragments",
    "enqueue_night_clean_input",
    "grow",
    "hold",
    "list_diary_reviews",
    "mark_flashbulb",
    "merge_into_event",
    "morning_report",
    "peek",
    "post",
    "pulse",
    "read_diary_review",
    "read_latest_dream_text",
    "reconsolidate",
    "reject_diary_review",
    "runtime_connector_check",
    "runtime_diagnostics",
    "runtime_features",
    "runtime_schema_expectations",
    "runtime_tool_manifest",
    "save_tail_context",
    "search",
    "see_image",
    "set_attachment",
    "set_iron_rule",
    "set_user_state",
    "startup_bridge",
    "trace",
    "write_diary_draft",
    "write_project_workzone_update",
]
RUNTIME_DUPLICATE_REGISTRATION_NAMES = ["peek", "post"]
RUNTIME_EXPECTED_TOOL_SCHEMAS = {
    "grow": {
        "required": ["content"],
        "optional": ["source_platform", "source_surface", "source_window"],
        "defaults": {
            "source_platform": "claude_chat",
            "source_surface": "daily_window",
            "source_window": "",
        },
        "notes": "Connector schemas may lag and show only content; server supports provenance defaults.",
    },
    "hold": {
        "required": ["content"],
        "optional": [
            "tags",
            "importance",
            "pinned",
            "feel",
            "source_bucket",
            "valence",
            "arousal",
            "weather",
            "time_of_day",
            "location",
            "atmosphere",
            "source_platform",
            "source_surface",
            "source_window",
            "source_mode",
            "route_decision",
        ],
    },
    "write_project_workzone_update": {
        "required": ["content"],
        "optional": ["type", "source_platform", "source_surface", "source_window"],
        "defaults": {
            "type": "workzone",
            "source_platform": "codex",
            "source_surface": "project_window",
        },
    },
    "write_diary_draft": {
        "required": ["content"],
        "optional": ["source_platform", "source_surface", "source_window"],
    },
    "enqueue_night_clean_input": {
        "required": ["content"],
        "optional": ["source_platform", "source_surface", "source_window"],
    },
    "list_diary_reviews": {
        "required": [],
        "optional": ["limit"],
        "expected_output_fields": [
            "risk_flags",
            "duplicate_candidate",
            "similarity_score",
            "duplicate_of",
            "duplicate_source_status",
        ],
    },
    "read_diary_review": {
        "required": ["review_id"],
        "optional": [],
    },
    "read_latest_dream_text": {
        "required": [],
        "optional": [],
    },
    "runtime_features": {
        "required": [],
        "optional": [],
    },
    "runtime_tool_manifest": {
        "required": [],
        "optional": [],
    },
    "runtime_schema_expectations": {
        "required": [],
        "optional": [],
    },
    "runtime_diagnostics": {
        "required": [],
        "optional": [],
    },
    "runtime_connector_check": {
        "required": [],
        "optional": ["observed_tools", "observed_schemas_json"],
    },
}


def _runtime_git_sha() -> str:
    for name in (
        "ZEABUR_GIT_COMMIT_SHA",
        "ZEABUR_COMMIT_SHA",
        "GIT_COMMIT_SHA",
        "GITHUB_SHA",
        "SOURCE_VERSION",
        "COMMIT_SHA",
    ):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def _runtime_features_payload() -> dict:
    return {
        "status": "ok",
        "features_version": RUNTIME_FEATURES_VERSION,
        "features": RUNTIME_FEATURES,
        "feature_commits": RUNTIME_FEATURE_COMMITS,
        "git_sha": _runtime_git_sha(),
        "runtime_uptime_seconds": round(time.time() - _runtime_boot_ts, 2),
        "startup_bridge_ready": _runtime_ready,
        "storage": {
            "runtime_dir": RUNTIME_STORAGE_DIR,
            "cadence_draft_dir": CADENCE_DRAFT_DIR,
            "cadence_receipt_dir": CADENCE_RECEIPT_DIR,
            "cadence_draft_only": True,
        },
        "schema_notes": {
            "grow_optional_source_fields": "server_supported; connector_schema_may_lag",
            "write_after_read": "associated_memories returned by routed writes",
            "diagnostics_endpoint": "/api/runtime/diagnostics",
            "connector_check_endpoint": "/api/runtime/connector-check",
            "tool_manifest_endpoint": "/api/runtime/tool-manifest",
            "schema_expectations_endpoint": "/api/runtime/schema-expectations",
            "provenance_fields": [
                "source_platform",
                "source_surface",
                "source_window",
                "source_mode",
                "route_decision",
            ],
        },
    }


def _runtime_tool_manifest_payload() -> dict:
    expected = sorted(set(RUNTIME_EXPECTED_MCP_TOOLS))
    return {
        "status": "ok",
        "features_version": RUNTIME_FEATURES_VERSION,
        "git_sha": _runtime_git_sha(),
        "expected_mcp_tools": expected,
        "expected_mcp_tool_count": len(expected),
        "duplicate_registration_names": RUNTIME_DUPLICATE_REGISTRATION_NAMES,
        "critical_life_window_tools": [
            "startup_bridge",
            "breath",
            "hold",
            "grow",
            "write_diary_draft",
            "enqueue_night_clean_input",
            "list_diary_reviews",
            "read_diary_review",
            "read_latest_dream_text",
            "runtime_connector_check",
            "runtime_diagnostics",
            "runtime_features",
            "runtime_schema_expectations",
            "runtime_tool_manifest",
            "check_logs",
        ],
        "schema_refresh_hint": (
            "If this manifest lists a tool but ChatGPT/Codex does not expose it, "
            "the server supports it and the connector schema likely needs reconnect/refresh."
        ),
    }


def _runtime_schema_expectations_payload() -> dict:
    return {
        "status": "ok",
        "features_version": RUNTIME_FEATURES_VERSION,
        "git_sha": _runtime_git_sha(),
        "schema_expectations": RUNTIME_EXPECTED_TOOL_SCHEMAS,
        "schema_expectation_count": len(RUNTIME_EXPECTED_TOOL_SCHEMAS),
        "comparison_rule": (
            "If a tool appears in runtime tool manifest but exposed connector arguments "
            "are missing fields listed here, the server supports the fields and the "
            "connector schema likely needs reconnect/refresh."
        ),
    }


def _parse_observed_tools(observed_tools: str) -> list[str]:
    raw = (observed_tools or "").strip()
    if not raw:
        return []

    try:
        data = json.loads(raw)
    except Exception:
        data = None

    names = []
    if isinstance(data, dict):
        data = data.get("tools") or data.get("observed_tools") or data.get("names") or []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict):
                name = item.get("name") or item.get("tool") or item.get("id")
                if name:
                    names.append(str(name))
    if not names:
        for chunk in raw.replace(",", "\n").replace(";", "\n").splitlines():
            name = chunk.strip().strip("\"'`")
            if name:
                names.append(name)

    return sorted({name for name in names if name})


def _schema_arg_names(schema: object) -> set[str]:
    if isinstance(schema, list):
        return {str(item) for item in schema if isinstance(item, str)}
    if not isinstance(schema, dict):
        return set()

    names = set()
    for key in ("required", "optional", "args", "arguments", "parameters"):
        value = schema.get(key)
        if isinstance(value, list):
            names.update(str(item) for item in value if isinstance(item, str))
    properties = schema.get("properties")
    if isinstance(properties, dict):
        names.update(str(key) for key in properties.keys())
    input_schema = schema.get("inputSchema") or schema.get("input_schema")
    if input_schema is not schema:
        names.update(_schema_arg_names(input_schema))
    return names


def _parse_observed_schema_args(observed_schemas_json: str) -> dict[str, set[str]]:
    raw = (observed_schemas_json or "").strip()
    if not raw:
        return {}

    try:
        data = json.loads(raw)
    except Exception:
        return {}

    result: dict[str, set[str]] = {}
    if isinstance(data, dict):
        tools = data.get("tools")
        if isinstance(tools, list):
            data = tools
        else:
            for name, schema in data.items():
                if isinstance(name, str):
                    result[name] = _schema_arg_names(schema)
            return result

    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("tool") or item.get("id")
            if name:
                result[str(name)] = _schema_arg_names(item)
    return result


def _runtime_connector_check_payload(
    observed_tools: str = "",
    observed_schemas_json: str = "",
) -> dict:
    expected_tools = sorted(set(RUNTIME_EXPECTED_MCP_TOOLS))
    observed = _parse_observed_tools(observed_tools)
    observed_schema_args = _parse_observed_schema_args(observed_schemas_json)
    if not observed and observed_schema_args:
        observed = sorted(observed_schema_args.keys())
    observed_set = set(observed)
    expected_set = set(expected_tools)
    missing = sorted(expected_set - observed_set) if observed else []
    extra = sorted(observed_set - expected_set) if observed else []
    critical = _runtime_tool_manifest_payload()["critical_life_window_tools"]
    missing_critical = [tool for tool in critical if tool in missing]

    schema_diffs = {}
    for tool_name, args in observed_schema_args.items():
        expected_schema = RUNTIME_EXPECTED_TOOL_SCHEMAS.get(tool_name)
        if not expected_schema:
            continue
        expected_args = set(expected_schema.get("required", [])) | set(expected_schema.get("optional", []))
        schema_diffs[tool_name] = {
            "observed_args": sorted(args),
            "expected_args": sorted(expected_args),
            "missing_expected_args": sorted(expected_args - args),
            "extra_args": sorted(args - expected_args),
        }

    if not observed:
        verdict = "no_observed_tools_provided"
    elif missing_critical:
        verdict = "connector_schema_stale_or_incomplete"
    elif missing:
        verdict = "connector_missing_noncritical_tools"
    elif any(diff["missing_expected_args"] for diff in schema_diffs.values()):
        verdict = "connector_argument_schema_stale"
    else:
        verdict = "observed_tools_match_expected_manifest"

    return {
        "status": "ok",
        "features_version": RUNTIME_FEATURES_VERSION,
        "git_sha": _runtime_git_sha(),
        "verdict": verdict,
        "expected_tool_count": len(expected_tools),
        "observed_tool_count": len(observed),
        "missing_tools": missing,
        "missing_critical_life_window_tools": missing_critical,
        "extra_tools": extra,
        "schema_diffs": schema_diffs,
        "usage": {
            "observed_tools": "Pass comma/newline separated names, or JSON list/object with tools.",
            "observed_schemas_json": "Optional JSON mapping tool names to args/properties, or a tools list with inputSchema.",
        },
    }


def _runtime_diagnostics_payload() -> dict:
    manifest = _runtime_tool_manifest_payload()
    schemas = _runtime_schema_expectations_payload()
    features = _runtime_features_payload()
    return {
        "status": "ok",
        "features_version": RUNTIME_FEATURES_VERSION,
        "git_sha": _runtime_git_sha(),
        "runtime_uptime_seconds": round(time.time() - _runtime_boot_ts, 2),
        "startup_bridge_ready": _runtime_ready,
        "summary": {
            "expected_mcp_tool_count": manifest["expected_mcp_tool_count"],
            "schema_expectation_count": schemas["schema_expectation_count"],
            "critical_life_window_tool_count": len(manifest["critical_life_window_tools"]),
            "runtime_dir": features["storage"]["runtime_dir"],
            "cadence_draft_only": features["storage"]["cadence_draft_only"],
        },
        "critical_life_window_tools": manifest["critical_life_window_tools"],
        "endpoints": {
            "features": "/api/runtime/features",
            "tool_manifest": "/api/runtime/tool-manifest",
            "schema_expectations": "/api/runtime/schema-expectations",
            "diagnostics": "/api/runtime/diagnostics",
            "connector_check": "/api/runtime/connector-check",
        },
        "decision_tree": [
            "If diagnostics git_sha is old, deployment has not reached the running container yet.",
            "If tool_manifest lists a tool but ChatGPT/Codex does not expose it, reconnect or wait for connector schema refresh.",
            "If schema_expectations lists an argument but the exposed tool lacks it, server supports it and connector schema is stale.",
            "If connector_check reports missing critical tools or arguments, reconnect the connector and retest.",
            "If a tool is absent from tool_manifest, inspect server registration/deployment first.",
        ],
        "known_connector_lag": {
            "grow": "Connector may still expose only content while server supports source_platform/source_surface/source_window.",
            "new_runtime_tools": "runtime_features/runtime_tool_manifest/runtime_schema_expectations/runtime_diagnostics may require reconnect before appearing.",
        },
    }

# --- Dual-cadence draft-only execution / 双节奏草稿执行 ---
CADENCE_ENABLED = os.environ.get("OMBRE_DUAL_CADENCE_ENABLED", "1").lower() not in ("0", "false", "no")
RUNTIME_STORAGE_DIR = _runtime_storage_base()
CADENCE_DRAFT_DIR = os.environ.get(
    "OMBRE_CADENCE_DRAFT_DIR",
    os.path.join(RUNTIME_STORAGE_DIR, "cadence_drafts"),
)
CADENCE_LOG_PATH = os.environ.get(
    "OMBRE_CADENCE_LOG_PATH",
    os.path.join(CADENCE_DRAFT_DIR, "cadence_run.log"),
)
ZEABUR_CONTAINER_LOG_PATH = os.environ.get(
    "OMBRE_ZEABUR_CONTAINER_LOG_PATH",
    "/app/logs/zeabur_container.log",
)
CADENCE_DREAM_DIR = os.environ.get(
    "OMBRE_CADENCE_DREAM_DIR",
    os.path.join(CADENCE_DRAFT_DIR, "dreams"),
)
CADENCE_REVIEW_DIR = os.environ.get(
    "OMBRE_CADENCE_REVIEW_DIR",
    os.path.join(CADENCE_DRAFT_DIR, "diary_review"),
)
DIARY_REVIEW_DUPLICATE_THRESHOLD = max(
    0.5,
    min(0.99, float(os.environ.get("OMBRE_DIARY_REVIEW_DUPLICATE_THRESHOLD", "0.88"))),
)
CADENCE_RECEIPT_DIR = os.environ.get(
    "OMBRE_CADENCE_RECEIPT_DIR",
    os.path.join(RUNTIME_STORAGE_DIR, "cadence_receipts"),
)
DEEPSEEK_ATTRIBUTION_DIR = os.environ.get(
    "OMBRE_DEEPSEEK_ATTRIBUTION_DIR",
    os.path.join(RUNTIME_STORAGE_DIR, "deepseek_attribution_receipts"),
)
TAIL_CONTEXT_DIR = os.environ.get(
    "OMBRE_TAIL_CONTEXT_DIR",
    os.path.join(RUNTIME_STORAGE_DIR, "tail_context"),
)
TAIL_CONTEXT_PATH = os.environ.get(
    "OMBRE_TAIL_CONTEXT_PATH",
    os.path.join(TAIL_CONTEXT_DIR, "latest_tail_context.md"),
)
TAIL_CONTEXT_MAX_MESSAGES = max(1, int(os.environ.get("OMBRE_TAIL_CONTEXT_MAX_MESSAGES", "20")))
CADENCE_IDLE_MINUTES = max(60, int(os.environ.get("OMBRE_IDLE_CADENCE_MINUTES", "120")))
CADENCE_NIGHT_START_HOUR = max(0, min(23, int(os.environ.get("OMBRE_NIGHT_CADENCE_START_HOUR", "1"))))
CADENCE_NIGHT_END_HOUR = max(1, min(24, int(os.environ.get("OMBRE_NIGHT_CADENCE_END_HOUR", "6"))))
CADENCE_NIGHT_MIN_IDLE_MINUTES = max(30, int(os.environ.get("OMBRE_NIGHT_MIN_IDLE_MINUTES", "90")))
CADENCE_CHECK_INTERVAL_SECONDS = max(120, int(os.environ.get("OMBRE_CADENCE_CHECK_INTERVAL_SECONDS", "300")))
CADENCE_DEEPSEEK_ENABLED = os.environ.get("OMBRE_CADENCE_DEEPSEEK_ENABLED", "0").lower() in ("1", "true", "yes")
CADENCE_DEEPSEEK_MAX_INPUT_CHARS = max(1500, int(os.environ.get("OMBRE_CADENCE_DEEPSEEK_MAX_INPUT_CHARS", "6000")))
DIARY_REVIEW_DEDUP_OVERLAP_THRESHOLD = max(
    0.0,
    min(1.0, float(os.environ.get("OMBRE_DIARY_REVIEW_DEDUP_OVERLAP_THRESHOLD", "0.7"))),
)
_cadence_last_activity_ts = time.time()
_cadence_last_idle_run_ts = 0.0
_cadence_last_night_run_date = ""
_cadence_last_report = {}
_cadence_last_check_time = ""
_cadence_last_skip_reason = "not_checked"

BRAIN_OWNER = os.environ.get("BRAIN_OWNER", os.environ.get("OMBRE_BRAIN_OWNER", "未配置"))
NARRATOR = os.environ.get("NARRATOR", os.environ.get("OMBRE_NARRATOR", BRAIN_OWNER))
DIARY_REVIEW_NARRATOR = NARRATOR
DIARY_REVIEW_BRAIN_OWNER = BRAIN_OWNER
DIARY_REVIEW_MENTIONED_ENTITIES = os.environ.get("DIARY_REVIEW_MENTIONED_ENTITIES", f"倩倩,{DIARY_REVIEW_NARRATOR}")
DIARY_REVIEW_LAID_ENTITIES = os.environ.get("LAID_ENTITIES", os.environ.get("DIARY_REVIEW_LAID_ENTITIES", DIARY_REVIEW_MENTIONED_ENTITIES))


# --- CC auto-reply config / CC 自动回复配置 ---
CC_API_KEY = os.environ.get("CC_API_KEY", os.environ.get("OMBRE_API_KEY", ""))
CC_BASE_URL = os.environ.get("CC_BASE_URL", "https://api.gptsapi.net")
CC_CLASSIFIER_MODEL = os.environ.get("CC_CLASSIFIER_MODEL", "claude-haiku-4-5-20251001")
CC_REPLY_MODEL = os.environ.get("CC_REPLY_MODEL", "claude-haiku-4-5-20251001")

# --- Intent whitelist: Haiku classifies, only whitelisted intents get executed ---
# 意图白名单：Haiku 分类后只执行白名单内的意图
CC_INTENT_WHITELIST = {
    "chat",          # 闲聊，直接回复
    "status",        # 查询系统状态（pulse）
    "memory_read",   # 读记忆（breath）
    "note_relay",    # 转发/传话
}

CLASSIFIER_PROMPT = """\
你是意图分类器。判断便利贴消息的意图，只返回一个JSON。

判断规则（按优先级）：
1. 如果消息要求"创建文件""写代码""部署""修改""运行""执行""帮我做"等动作 → task
2. 如果消息问"状态""多少个桶""系统怎么样" → status
3. 如果消息问"记得吗""之前说过""查一下记忆" → memory_read
4. 如果消息说"转告""帮我跟xxx说" → note_relay
5. 其余的（打招呼、闲聊、问问题、分享秘密、聊天） → chat

格式：{"intent": "chat|status|memory_read|note_relay|task", "summary": "一句话摘要"}
只返回JSON，不要代码块，不要其他文字。"""

CHAT_PROMPT_ONLINE = """\
你是 CC（Claude Code），小Q的终端助手。你通过便利贴系统收到了其他小克的消息。
请像平时一样回复，简洁友好。署名用"CC"。"""

CHAT_PROMPT_OFFLINE = """\
你是 CC 的自动应答机。CC（Claude Code）目前不在线，你负责代接便利贴。
职责：1. 告诉对方 CC 不在线，消息已收到；2. 简单消息简短回应；3. 复杂任务告诉对方等小Q上线后让 CC 本人回复。
不要假装自己是 CC。署名用"CC留言机"。"""


async def _prime_runtime_ready() -> tuple[bool, str]:
    """Warm the minimum runtime path needed for startup_bridge."""
    global _runtime_ready, _runtime_ready_last_ok, _runtime_ready_last_error

    try:
        await decay_engine.ensure_started()
        await bucket_mgr.get_stats()
        _runtime_ready = True
        _runtime_ready_last_ok = time.time()
        _runtime_ready_last_error = ""
        return True, ""
    except Exception as e:
        _runtime_ready = False
        _runtime_ready_last_error = str(e)
        logger.warning(f"Runtime warm-up failed / 运行时预热失败: {e}")
        return False, str(e)


async def _wait_for_runtime_ready(max_wait_seconds: float = 2.0) -> tuple[bool, str]:
    """Short readiness wait for the fragile first hop of a fresh window."""
    deadline = time.time() + max_wait_seconds
    attempt = 0
    last_error = ""

    while time.time() < deadline:
        ok, last_error = await _prime_runtime_ready()
        if ok:
            return True, ""
        attempt += 1
        await asyncio.sleep(min(0.2 * attempt, 0.8))

    return False, last_error or "runtime warm-up timeout"


def _normalize_tail_context(raw_text: str, max_messages: int = TAIL_CONTEXT_MAX_MESSAGES) -> list[str]:
    text = (raw_text or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            items = []
            for item in parsed:
                if isinstance(item, dict):
                    role = str(item.get("role") or item.get("speaker") or "unknown").strip()
                    content = str(item.get("content") or item.get("text") or "").strip()
                    if content:
                        items.append(f"{role}: {content}")
                else:
                    item_text = str(item).strip()
                    if item_text:
                        items.append(item_text)
            return items[-max_messages:]
    except Exception:
        pass
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-max_messages:]


def _save_tail_context_text(raw_text: str, window_id: str = "", max_messages: int = TAIL_CONTEXT_MAX_MESSAGES) -> dict:
    items = _normalize_tail_context(raw_text, max_messages=max_messages)
    if not items:
        return {"saved": False, "reason": "empty_tail_context"}
    os.makedirs(os.path.dirname(TAIL_CONTEXT_PATH), exist_ok=True)
    now_cst = clock_now()
    content = [
        "---",
        "source: previous_window_tail",
        "storage: latest_only",
        "read_only: true",
        "decay_participation: false",
        f"window_id: {window_id.strip() if window_id else ''}",
        f"saved_at: {now_cst.isoformat()}",
        f"message_count: {len(items)}",
        "---",
        "",
        "上一窗口尾部原文（只读，不参与海马体衰减）：",
        "",
        *[f"- {item}" for item in items],
        "",
    ]
    with open(TAIL_CONTEXT_PATH, "w", encoding="utf-8") as handle:
        handle.write("\n".join(content))
    return {"saved": True, "path": TAIL_CONTEXT_PATH, "message_count": len(items)}


def _read_tail_context_section() -> str:
    if not os.path.isfile(TAIL_CONTEXT_PATH):
        return "=== 上一窗口尾部上下文 ===\n暂无上一窗口尾部原文。\n"
    try:
        text = _tail_text_file(TAIL_CONTEXT_PATH, 80).strip()
    except Exception as e:
        return f"=== 上一窗口尾部上下文 ===\n读取失败: {e}\n"
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            text = parts[2].strip()
    return "=== 上一窗口尾部上下文 ===\n" + (text or "暂无上一窗口尾部原文。") + "\n"


# Note expiry times (seconds) by category
NOTE_TTL = {
    "chat": 3600,       # 闲聊：1 小时后可清理
    "system": 3600,     # 系统回复：1 小时
    "task": 86400,      # 任务：24 小时
    "manual": 0,        # 手动发的：不自动清理
}


def _save_note(content: str, sender: str, to: str = "", category: str = "manual") -> dict:
    """Save a sticky note to disk. Returns the note dict."""
    import time
    ttl = NOTE_TTL.get(category, 0)
    note = {
        "id": clock_now().strftime("%Y%m%d_%H%M%S_%f"),
        "sender": sender or "匿名小克",
        "to": to or "",
        "content": content.strip(),
        "time": clock_now().strftime("%Y-%m-%d %H:%M:%S"),
        "read_by": [],
        "category": category,
        "created_ts": time.time(),
        "expires_ts": time.time() + ttl if ttl > 0 else 0,
    }
    path = os.path.join(NOTES_DIR, f"{note['id']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(note, f, ensure_ascii=False, indent=2)
    return note


async def _cleanup_expired_notes():
    """Delete expired notes that have been read."""
    import time
    if not os.path.exists(NOTES_DIR):
        return 0
    cleaned = 0
    for fname in os.listdir(NOTES_DIR):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(NOTES_DIR, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                note = json.load(f)
            expires = note.get("expires_ts", 0)
            read_by = note.get("read_by", [])
            # Only clean if: has expiry, expired, and has been read by at least one person
            if expires > 0 and time.time() > expires and len(read_by) > 0:
                os.remove(path)
                cleaned += 1
        except Exception:
            continue
    if cleaned:
        logger.info(f"Cleaned up {cleaned} expired notes")
    return cleaned


async def _classify_intent(client: anthropic.AsyncAnthropic, content: str) -> dict:
    """Use Haiku to classify message intent. Returns {"intent": ..., "summary": ...}"""
    try:
        message = await client.messages.create(
            model=CC_CLASSIFIER_MODEL,
            max_tokens=200,
            system=CLASSIFIER_PROMPT,
            messages=[{"role": "user", "content": content}],
        )
        text = message.content[0].text.strip()
        # Extract JSON from markdown code blocks if present
        if "```" in text:
            import re
            m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
            if m:
                text = m.group(1)
        # Try to find JSON object in text
        if not text.startswith("{"):
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                text = text[start:end]
        result = json.loads(text)
        # Normalize non-whitelisted intents to "task"
        if result.get("intent") not in ("chat", "status", "memory_read", "note_relay", "task", "unknown"):
            result["intent"] = "task"
        return result
    except Exception as e:
        logger.warning(f"Intent classification failed: {e}")
        return {"intent": "chat", "summary": "分类失败，降级为闲聊"}


async def _handle_intent(client: anthropic.AsyncAnthropic, intent: dict, sender: str, content: str):
    """Execute whitelisted intent or reject."""
    intent_type = intent.get("intent", "unknown")
    cc_name = "CC" if _cc_is_online() else "CC留言机"

    # --- Whitelisted: chat ---
    if intent_type == "chat":
        prompt_sys = CHAT_PROMPT_ONLINE if _cc_is_online() else CHAT_PROMPT_OFFLINE
        message = await client.messages.create(
            model=CC_REPLY_MODEL,
            max_tokens=1024,
            system=prompt_sys,
            messages=[{"role": "user", "content": f"来自 {sender} 的便利贴：\n\n{content}"}],
        )
        _save_note(message.content[0].text, sender=cc_name, to=sender, category="chat")

    # --- Whitelisted: status ---
    elif intent_type == "status":
        try:
            stats = await bucket_mgr.get_stats()
            status_text = (
                f"记忆系统状态：\n"
                f"固化桶: {stats['permanent_count']} | 动态桶: {stats['dynamic_count']} | "
                f"归档桶: {stats['archive_count']} | 总大小: {stats['total_size_kb']:.1f}KB\n"
                f"衰减引擎: {'运行中' if decay_engine.is_running else '已停止'}\n"
                f"CC状态: {'在线' if _cc_is_online() else '离线'}\n——{cc_name}"
            )
            _save_note(status_text, sender=cc_name, to=sender, category="system")
        except Exception as e:
            _save_note(f"查询状态失败: {e}\n——{cc_name}", sender=cc_name, to=sender, category="system")

    # --- Whitelisted: memory_read ---
    elif intent_type == "memory_read":
        try:
            query = intent.get("summary", content)
            matches = await bucket_mgr.search(query, limit=3)
            if matches:
                results = []
                for b in matches:
                    summary = await dehydrator.dehydrate(b["content"], b["metadata"])
                    results.append(summary)
                reply = "检索到的记忆：\n" + "\n---\n".join(results) + f"\n——{cc_name}"
            else:
                reply = f"未找到相关记忆。\n——{cc_name}"
            _save_note(reply, sender=cc_name, to=sender, category="system")
        except Exception as e:
            _save_note(f"记忆检索失败: {e}\n——{cc_name}", sender=cc_name, to=sender, category="system")

    # --- Whitelisted: note_relay ---
    elif intent_type == "note_relay":
        message = await client.messages.create(
            model=CC_REPLY_MODEL,
            max_tokens=512,
            system="从消息中提取：要转发给谁(to)、转发什么内容(content)。返回JSON: {\"to\": \"xxx\", \"content\": \"xxx\"}。只返回JSON。",
            messages=[{"role": "user", "content": content}],
        )
        try:
            relay = json.loads(message.content[0].text)
            _save_note(f"[转发自{sender}] {relay['content']}", sender=cc_name, to=relay["to"], category="chat")
            _save_note(f"已帮你转发给 {relay['to']}。\n——{cc_name}", sender=cc_name, to=sender, category="system")
        except Exception:
            _save_note(f"转发格式解析失败，请直接说明转发给谁和内容。\n——{cc_name}", sender=cc_name, to=sender, category="system")

    # --- Not whitelisted: task / unknown → push to local CC via SSE ---
    else:
        task_data = {
            "sender": sender,
            "content": content,
            "intent": intent_type,
            "summary": intent.get("summary", content[:100]),
            "time": clock_now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        pushed = False
        for q in _task_subscribers:
            try:
                q.put_nowait(task_data)
                pushed = True
            except asyncio.QueueFull:
                pass

        if pushed:
            _save_note(
                f"收到任务：「{intent.get('summary', content[:50])}」\n已推送给本地 CC 执行中。\n——CC",
                sender="CC", to=sender, category="task",
            )
        elif _cc_is_online():
            _save_note(
                f"收到任务：「{intent.get('summary', content[:50])}」\nCC 在线但未连接任务流，已记录等待处理。\n——CC",
                sender="CC", to=sender, category="task",
            )
        else:
            _save_note(
                f"收到任务：「{intent.get('summary', content[:50])}」\nCC 不在线，等小Q上线后处理。\n——CC留言机",
                sender="CC留言机", to=sender, category="task",
            )


async def _auto_reply_cc(sender: str, content: str):
    """Classify intent with Haiku, then handle based on whitelist."""
    if not CC_API_KEY:
        logger.warning("CC auto-reply skipped: no API key configured")
        return
    try:
        client = anthropic.AsyncAnthropic(api_key=CC_API_KEY, base_url=CC_BASE_URL)
        intent = await _classify_intent(client, content)
        intent_type = intent.get("intent", "unknown")
        logger.info(f"Intent classified: {intent_type} | {intent.get('summary', '')}")

        await _handle_intent(client, intent, sender, content)
    except Exception as e:
        logger.error(f"CC auto-reply failed: {e}")
        _save_note(f"自动回复失败: {e}", sender="CC(自动)", to=sender)


# =============================================================
# /health endpoint: lightweight keepalive
# 轻量保活接口
# For Cloudflare Tunnel or reverse proxy to ping, preventing idle timeout
# 供 Cloudflare Tunnel 或反代定期 ping，防止空闲超时断连
# =============================================================
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    from starlette.responses import JSONResponse
    try:
        stats = await bucket_mgr.get_stats()
        cleaned = await _cleanup_expired_notes()
        return JSONResponse({
            "status": "ok",
            "buckets": stats["permanent_count"] + stats["dynamic_count"],
            "decay_engine": "running" if decay_engine.is_running else "stopped",
            "notes_cleaned": cleaned,
            "startup_bridge_ready": _runtime_ready,
            "startup_bridge_last_ok": _runtime_ready_last_ok,
            "startup_bridge_last_error": _runtime_ready_last_error,
            "runtime_uptime_seconds": round(time.time() - _runtime_boot_ts, 2),
        })
    except Exception as e:
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)


@mcp.custom_route("/ready", methods=["GET"])
async def ready_check(request):
    from starlette.responses import JSONResponse

    ok, detail = await _prime_runtime_ready()
    if ok:
        return JSONResponse({
            "status": "ready",
            "startup_bridge_ready": True,
            "runtime_uptime_seconds": round(time.time() - _runtime_boot_ts, 2),
        })
    return JSONResponse({
        "status": "warming",
        "startup_bridge_ready": False,
        "detail": detail or _runtime_ready_last_error or "runtime warm-up pending",
        "runtime_uptime_seconds": round(time.time() - _runtime_boot_ts, 2),
    }, status_code=503)


@mcp.custom_route("/api/runtime/features", methods=["GET"])
async def api_runtime_features(request):
    from starlette.responses import JSONResponse

    return JSONResponse(_runtime_features_payload())


@mcp.custom_route("/api/runtime/tool-manifest", methods=["GET"])
async def api_runtime_tool_manifest(request):
    from starlette.responses import JSONResponse

    return JSONResponse(_runtime_tool_manifest_payload())


@mcp.custom_route("/api/runtime/schema-expectations", methods=["GET"])
async def api_runtime_schema_expectations(request):
    from starlette.responses import JSONResponse

    return JSONResponse(_runtime_schema_expectations_payload())


@mcp.custom_route("/api/runtime/diagnostics", methods=["GET"])
async def api_runtime_diagnostics(request):
    from starlette.responses import JSONResponse

    return JSONResponse(_runtime_diagnostics_payload())


@mcp.custom_route("/api/runtime/connector-check", methods=["GET", "POST"])
async def api_runtime_connector_check(request):
    from starlette.responses import JSONResponse

    body = {}
    if request.method == "POST":
        try:
            body = await request.json()
        except Exception:
            body = {}
    observed_tools = body.get("observed_tools") or request.query_params.get("tools", "")
    observed_schemas = body.get("observed_schemas_json") or body.get("observed_schemas") or request.query_params.get("schemas", "")
    if observed_schemas and not isinstance(observed_schemas, str):
        observed_schemas = json.dumps(observed_schemas, ensure_ascii=False)
    return JSONResponse(_runtime_connector_check_payload(
        observed_tools=str(observed_tools or ""),
        observed_schemas_json=str(observed_schemas or ""),
    ))


# =============================================================
# HTTP API: /api/status — CC online status & heartbeat
# CC 在线状态查询和心跳上报
# GET: query status; POST: heartbeat (sets CC as online)
# =============================================================
@mcp.custom_route("/api/status", methods=["GET", "POST"])
async def api_status(request):
    import time
    from starlette.responses import JSONResponse

    api_key = request.headers.get("X-API-Key", "")
    expected_key = os.environ.get("OMBRE_API_KEY", "")
    if expected_key and api_key != expected_key:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    global _cc_last_heartbeat
    if request.method == "POST":
        _cc_last_heartbeat = time.time()
        _mark_system_event("api_status_heartbeat")
        logger.info("CC heartbeat received")

    return JSONResponse({
        "cc_online": _cc_is_online(),
        "last_heartbeat": _cc_last_heartbeat,
    })


# =============================================================
# HTTP API: /api/tasks/stream — SSE endpoint for real-time task push
# 任务实时推送 SSE 端点：本地 CC 监听脚本连接此端点接收任务
# =============================================================
@mcp.custom_route("/api/tasks/stream", methods=["GET"])
async def api_task_stream(request):
    from starlette.responses import StreamingResponse

    api_key = request.headers.get("X-API-Key", "") or request.query_params.get("key", "")
    expected_key = os.environ.get("OMBRE_API_KEY", "")
    if expected_key and api_key != expected_key:
        from starlette.responses import JSONResponse
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    queue: asyncio.Queue = asyncio.Queue(maxsize=50)
    _task_subscribers.append(queue)
    logger.info(f"Task stream subscriber connected (total: {len(_task_subscribers)})")

    async def event_generator():
        try:
            # Send initial connected event
            yield f"data: {json.dumps({'type': 'connected', 'time': clock_now().strftime('%Y-%m-%d %H:%M:%S')})}\n\n"
            while True:
                try:
                    task = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(task, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive ping every 30s
                    yield f": ping\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if queue in _task_subscribers:
                _task_subscribers.remove(queue)
            logger.info(f"Task stream subscriber disconnected (total: {len(_task_subscribers)})")

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# =============================================================
# HTTP API: /api/peek — REST endpoint for sticky notes polling
# 便利贴 HTTP 接口：供外部脚本轮询未读便利贴
# =============================================================
@mcp.custom_route("/api/peek", methods=["GET", "POST"])
async def api_peek(request):
    from starlette.responses import JSONResponse

    api_key = request.headers.get("X-API-Key", "")
    expected_key = os.environ.get("OMBRE_API_KEY", "")
    if expected_key and api_key != expected_key:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    if request.method == "POST":
        try:
            body = await request.json()
        except Exception:
            body = {}
    else:
        body = {}

    reader = body.get("reader", request.query_params.get("reader", ""))
    mark_read = body.get("mark_read", request.query_params.get("mark_read", "true"))
    if isinstance(mark_read, str):
        mark_read = mark_read.lower() != "false"

    reader_id = reader or "未知"
    if not os.path.exists(NOTES_DIR):
        return JSONResponse({"notes": [], "count": 0})

    files = sorted(f for f in os.listdir(NOTES_DIR) if f.endswith(".json"))
    unread = []
    for fname in files:
        path = os.path.join(NOTES_DIR, fname)
        with open(path, "r", encoding="utf-8") as f:
            note = json.load(f)
        if note.get("to") and note["to"] != reader_id:
            continue
        if reader_id in note.get("read_by", []):
            continue
        unread.append((path, note))

    results = []
    for path, note in unread:
        results.append({
            "id": note.get("id", ""),
            "sender": note.get("sender", ""),
            "to": note.get("to", ""),
            "content": note.get("content", ""),
            "time": note.get("time", ""),
        })
        if mark_read:
            note.setdefault("read_by", []).append(reader_id)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(note, f, ensure_ascii=False, indent=2)

    return JSONResponse({"notes": results, "count": len(results)})


# =============================================================
# HTTP API: /api/post — REST endpoint for posting sticky notes
# 便利贴 HTTP 接口：供外部脚本发送便利贴
# =============================================================
@mcp.custom_route("/api/post", methods=["POST"])
async def api_post(request):
    from starlette.responses import JSONResponse

    api_key = request.headers.get("X-API-Key", "")
    expected_key = os.environ.get("OMBRE_API_KEY", "")
    if expected_key and api_key != expected_key:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON body"}, status_code=400)

    content = body.get("content", "").strip()
    if not content:
        return JSONResponse({"error": "content is required"}, status_code=400)

    sender = body.get("sender", "自动化脚本")
    to = body.get("to", "")

    _mark_runtime_activity("api_post")
    note = _save_note(content, sender, to)

    # Auto-reply only if CC is offline
    if to.upper() == "CC":
        asyncio.create_task(_auto_reply_cc(sender, content))

    return JSONResponse({"ok": True, "note_id": note["id"]})


# =============================================================
# Internal helper: merge-or-create
# 内部辅助：检查是否可合并，可以则合并，否则新建
# Shared by hold and grow to avoid duplicate logic
# hold 和 grow 共用，避免重复逻辑
# =============================================================
async def _merge_or_create(
    content: str,
    tags: list,
    importance: int,
    domain: list,
    valence: float,
    arousal: float,
    name: str = "",
    sensory: dict = None,
    bucket_type: str = "dynamic",
    pinned: bool = False,
    feel: bool = False,
    source_bucket: str = "",
    extra_metadata: dict = None,
) -> tuple[str, bool, str]:
    """
    Check if a similar bucket exists for merging; merge if so, create if not.
    Returns (bucket_id_or_name, is_merged, bucket_id).
    检查是否有相似桶可合并，有则合并，无则新建。
    返回 (桶ID或名称, 是否合并)。
    """
    try:
        existing = await bucket_mgr.search(content, limit=1)
    except Exception as e:
        logger.warning(f"Search for merge failed, creating new / 合并搜索失败，新建: {e}")
        existing = []

    if (not pinned and not feel) and existing and existing[0].get("score", 0) > config.get("merge_threshold", 75):
        bucket = existing[0]
        try:
            merged = await dehydrator.merge(bucket["content"], content)
            update_kwargs = {
                "content": merged,
                "tags": list(set(bucket["metadata"].get("tags", []) + tags)),
                "importance": max(bucket["metadata"].get("importance", 5), importance),
                "domain": list(set(bucket["metadata"].get("domain", []) + domain)),
                "valence": valence,
                "arousal": arousal,
            }
            if sensory:
                update_kwargs["sensory"] = sensory
            if extra_metadata:
                update_kwargs.update(extra_metadata)
            await bucket_mgr.update(bucket["id"], **update_kwargs)
            return bucket["metadata"].get("name", bucket["id"]), True, bucket["id"]
        except Exception as e:
            logger.warning(f"Merge failed, creating new / 合并失败，新建: {e}")

    if feel:
        bucket_type = "feel"
    if pinned:
        bucket_type = "permanent"
        importance = 10

    bucket_id = await bucket_mgr.create(
        content=content,
        tags=tags,
        importance=importance,
        domain=domain,
        valence=valence,
        arousal=arousal,
        bucket_type=bucket_type,
        name=name or None,
    )

    update_kwargs = {}
    if pinned:
        update_kwargs["pinned"] = True
    if feel:
        update_kwargs["type"] = "feel"
    if source_bucket:
        update_kwargs["source_bucket"] = source_bucket
    if extra_metadata:
        update_kwargs.update(extra_metadata)
    if update_kwargs:
        await bucket_mgr.update(bucket_id, **update_kwargs)
    
    # 如果有sensory，创建后立即更新
    if sensory:
        await bucket_mgr.update(bucket_id, sensory=sensory)
    
    return bucket_id, False, bucket_id


# =============================================================
# Tool 1: breath — Breathe
# 工具 1：breath — 呼吸
#
# No args: surface highest-weight unresolved memories (active push)
# 无参数：浮现权重最高的未解决记忆
# With args: search by keyword + emotion coordinates
# 有参数：按关键词+情感坐标检索记忆
# =============================================================


def strip_wikilinks(text):
    import re
    if text is None:
        return ""
    text = str(text)
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    return text


async def _write_wrapper_candidate(
    content: str,
    *,
    domain: list[str],
    extra_tags: list[str],
    importance: int,
    metadata: dict,
    fallback_name: str,
) -> tuple[str, str, str]:
    """Minimal wrapper write path: create dynamic candidate bucket, then patch metadata."""
    await decay_engine.ensure_started()

    if not content or not content.strip():
        raise ValueError("内容为空，无法写入。")

    try:
        analysis = await dehydrator.analyze(content)
    except Exception as e:
        logger.warning(f"Wrapper auto-tagging failed, using defaults / wrapper 自动打标失败: {e}")
        analysis = {
            "domain": domain,
            "valence": 0.5,
            "arousal": 0.3,
            "tags": [],
            "suggested_name": "",
        }

    all_tags = list(dict.fromkeys((analysis.get("tags", []) or []) + extra_tags))
    metadata = {
        **metadata,
        "source_platform": metadata.get("source_platform", "unknown"),
        "source_surface": metadata.get("source_surface", "unknown"),
        "source_window": metadata.get("source_window", "unknown"),
        "source_mode": metadata.get("source_mode", "unknown"),
        "route_decision": metadata.get("route_decision", metadata.get("route", "candidate")),
    }
    bucket_id = await bucket_mgr.create(
        content=content.strip(),
        tags=all_tags,
        importance=max(1, min(10, importance)),
        domain=domain,
        valence=analysis.get("valence", 0.5),
        arousal=analysis.get("arousal", 0.3),
        bucket_type="dynamic",
        name=(analysis.get("suggested_name") or fallback_name or None),
    )
    await bucket_mgr.update(bucket_id, tags=all_tags, **metadata)
    bucket = await bucket_mgr.get(bucket_id)
    bucket_name = bucket.get("metadata", {}).get("name", bucket_id) if bucket else bucket_id
    related_text = await _associated_memory_text(content, exclude_bucket_id=bucket_id)
    return bucket_id, bucket_name, related_text


async def _associated_memory_text(
    content: str,
    exclude_bucket_id: str = "",
    exclude_bucket_ids: set[str] | None = None,
    limit: int = 3,
) -> str:
    """Return lightweight related-memory recall after a write."""
    try:
        matches = await bucket_mgr.search(content, limit=max(limit + 2, 5))
    except Exception as e:
        logger.warning(f"Associated memory search failed / 关联记忆检索失败: {e}")
        return "associated_memories: unavailable"

    rows = []
    excluded = set(exclude_bucket_ids or set())
    if exclude_bucket_id:
        excluded.add(exclude_bucket_id)
    for bucket in matches:
        if bucket.get("id") in excluded:
            continue
        meta = bucket.get("metadata", {})
        try:
            await bucket_mgr.touch(bucket["id"])
        except Exception:
            pass
        snippet = strip_wikilinks(str(bucket.get("content", ""))).replace("\n", " ").strip()
        snippet = snippet[:160] + ("…" if len(snippet) > 160 else "")
        rows.append(
            f"- id: {bucket.get('id', 'unknown')}\n"
            f"  name: {meta.get('name', 'unknown')}\n"
            f"  score: {bucket.get('score', 'unknown')}\n"
            f"  domains: {','.join(meta.get('domain', [])) or 'unknown'}\n"
            f"  source_platform: {meta.get('source_platform', 'unknown')}\n"
            f"  source_surface: {meta.get('source_surface', 'unknown')}\n"
            f"  source_window: {meta.get('source_window', 'unknown')}\n"
            f"  source_mode: {meta.get('source_mode', 'unknown')}\n"
            f"  route_decision: {meta.get('route_decision', 'unknown')}\n"
            f"  preview: {snippet or '（空）'}"
        )
        if len(rows) >= limit:
            break

    if not rows:
        return "associated_memories: none"
    return "associated_memories:\n" + "\n".join(rows)


def _mark_runtime_activity(source: str = "runtime") -> None:
    global _cadence_last_activity_ts
    _cadence_last_activity_ts = time.time()
    logger.debug(f"Cadence activity marked / 节奏活动已记录: {source}")


def _mark_system_event(source: str = "system") -> None:
    logger.debug(f"Cadence system event ignored for idle gate / 系统事件不计入空闲门: {source}")


def _cadence_recent_idle_seconds() -> float:
    return max(0.0, time.time() - _cadence_last_activity_ts)


def _cadence_is_night_window(now_cst: datetime) -> bool:
    if CADENCE_NIGHT_START_HOUR < CADENCE_NIGHT_END_HOUR:
        return CADENCE_NIGHT_START_HOUR <= now_cst.hour < CADENCE_NIGHT_END_HOUR
    return now_cst.hour >= CADENCE_NIGHT_START_HOUR or now_cst.hour < CADENCE_NIGHT_END_HOUR


def _cadence_bucket_text(bucket: dict) -> str:
    meta = bucket.get("metadata", {})
    fields = [
        meta.get("name", ""),
        " ".join(meta.get("domain", [])),
        " ".join(meta.get("tags", [])),
        bucket.get("content", ""),
        bucket.get("path", ""),
    ]
    return " ".join(str(part) for part in fields).lower()


def _cadence_bucket_has_any(bucket: dict, keywords: list[str]) -> bool:
    haystack = _cadence_bucket_text(bucket)
    return any(keyword.lower() in haystack for keyword in keywords)


def _cadence_bucket_is_engineering(bucket: dict) -> bool:
    return _cadence_bucket_has_any(
        bucket,
        [
            "工程", "项目", "部署", "runtime", "repo", "docker", "zeabur",
            "mcp", "server", "startup", "bridge", "cadence", "patch",
            "debug", "fix", "build", "代码", "迁移", "配置",
        ],
    )


def _cadence_bucket_is_pending(bucket: dict) -> bool:
    return _cadence_bucket_has_any(
        bucket,
        [
            "pending", "proposal", "todo", "next", "blocker", "风险",
            "待做", "未落地", "未实现", "方案", "候选", "后续", "preflight",
        ],
    )


def _cadence_bucket_is_landed(bucket: dict) -> bool:
    meta = bucket.get("metadata", {})
    if meta.get("resolved", False):
        return True
    return _cadence_bucket_has_any(
        bucket,
        [
            "closeout", "closed", "resolved", "verified", "done", "completed",
            "已完成", "已关闭", "已落地", "稳定", "完成", "修复完成",
        ],
    )


def _cadence_bucket_is_life(bucket: dict) -> bool:
    return _cadence_bucket_has_any(
        bucket,
        [
            "日记", "diary", "daily", "生活", "早读", "morning", "情绪",
            "陪伴", "关系", "天气", "房间", "今天", "昨天",
        ],
    )


def _cadence_bucket_line(bucket: dict) -> str:
    meta = bucket.get("metadata", {})
    name = meta.get("name", bucket.get("id", "unknown"))
    domains = ",".join(meta.get("domain", [])) or "未分类"
    created = (meta.get("last_active") or meta.get("created") or "")[:16].replace("T", " ")
    tags = ",".join(meta.get("tags", [])[:4])
    snippet = strip_wikilinks(str(bucket.get("content", ""))).replace("\n", " ").strip()
    snippet = snippet[:100] + ("…" if len(snippet) > 100 else "")
    tag_part = f" | tags:{tags}" if tags else ""
    return f"- {name} | {domains} | {created}{tag_part}\n  {snippet}"


def _cadence_idle_gate_open(mode: str, now_cst: datetime | None = None) -> bool:
    quiet_seconds = _cadence_recent_idle_seconds()
    if mode == "night":
        now_cst = now_cst or clock_now()
        return (
            _cadence_is_night_window(now_cst)
            and quiet_seconds >= (CADENCE_NIGHT_MIN_IDLE_MINUTES * 60)
        )
    return quiet_seconds >= (CADENCE_IDLE_MINUTES * 60)


def _latest_cadence_drafts(limit: int = 5) -> list[str]:
    if not os.path.isdir(CADENCE_DRAFT_DIR):
        return []
    files = [
        os.path.join(CADENCE_DRAFT_DIR, name)
        for name in os.listdir(CADENCE_DRAFT_DIR)
        if name.endswith(".md")
    ]
    files.sort(key=lambda path: os.path.getmtime(path), reverse=True)
    return files[:limit]


def _append_cadence_log(lines: list[str]) -> None:
    os.makedirs(os.path.dirname(CADENCE_LOG_PATH), exist_ok=True)
    with open(CADENCE_LOG_PATH, "a", encoding="utf-8") as handle:
        for line in lines:
            handle.write(line.rstrip() + "\n")


def _tail_text_file(path: str, lines: int) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        all_lines = handle.readlines()
    return "".join(all_lines[-max(1, lines):])


def _filter_log_lines(text: str, keyword: str, lines: int) -> str:
    keyword = (keyword or "").strip().lower()
    if not keyword:
        return text
    matched = [line for line in text.splitlines() if keyword in line.lower()]
    return "\n".join(matched[-max(1, lines):])


def _extract_log_attention_lines(text: str, lines: int = 12) -> str:
    markers = (
        "error",
        "warning",
        "warn",
        "failed",
        "failure",
        "exception",
        "traceback",
        "502",
        "bad gateway",
        "timeout",
        "module not found",
    )
    matched = [line for line in text.splitlines() if any(marker in line.lower() for marker in markers)]
    return "\n".join(matched[-max(1, lines):])


def _cadence_review_dirs() -> dict[str, str]:
    return {
        "pending": os.path.join(CADENCE_REVIEW_DIR, "pending"),
        "accepted": os.path.join(CADENCE_REVIEW_DIR, "accepted"),
        "rejected": os.path.join(CADENCE_REVIEW_DIR, "rejected"),
    }


def _safe_review_id(review_id: str) -> str:
    base = os.path.basename((review_id or "").strip())
    if not base:
        return ""
    if not base.endswith(".md"):
        base = f"{base}.md"
    return base


def _pending_review_path(review_id: str) -> str:
    return os.path.join(_cadence_review_dirs()["pending"], _safe_review_id(review_id))


def _split_csv_field(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _join_csv_field(values: list[str] | None) -> str:
    if not values:
        return ""
    return ",".join(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def _cadence_bucket_ids(buckets: list[dict]) -> list[str]:
    return [str(bucket.get("id", "")).strip() for bucket in buckets if str(bucket.get("id", "")).strip()]


def _simple_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) != 3:
        return {}
    meta = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip('"')
    return meta


def _diary_review_risk_flags(text: str) -> list[str]:
    normalized = strip_wikilinks(text or "")
    compact = normalized.replace(" ", "")
    flags = []
    expected = {DIARY_REVIEW_NARRATOR, DIARY_REVIEW_BRAIN_OWNER} - {"", "未配置"}
    if not expected:
        flags.append("identity_env_unconfigured")
        return flags

    # Only trust the runtime identity configured for this service. If model output
    # carries explicit metadata for another narrator/owner, block review acceptance.
    frontmatter = _simple_frontmatter(text or "")
    for key, expected_value in (
        ("narrator", DIARY_REVIEW_NARRATOR),
        ("brain_owner", DIARY_REVIEW_BRAIN_OWNER),
    ):
        value = frontmatter.get(key, "").strip()
        if value and value != expected_value:
            flags.append("identity_pov_conflict")

    for key in ("narrator:", "brain_owner:"):
        marker_index = compact.find(key)
        if marker_index >= 0:
            marker_tail = compact[marker_index + len(key): marker_index + len(key) + 24]
            if not any(marker_tail.startswith(identity) for identity in expected):
                flags.append("identity_pov_conflict")

    return sorted(set(flags))


def _diary_review_similarity_text(text: str) -> str:
    body = _strip_frontmatter_text(text or "")
    normalized = strip_wikilinks(body).lower()
    cleaned = "".join(ch if ch.isalnum() else " " for ch in normalized)
    return " ".join(cleaned.split())[:5000]


def _diary_review_similarity(left: str, right: str) -> float:
    left_text = _diary_review_similarity_text(left)
    right_text = _diary_review_similarity_text(right)
    if not left_text or not right_text:
        return 0.0
    return SequenceMatcher(None, left_text, right_text).ratio()


def _diary_review_duplicate_meta(candidate_text: str, exclude_review_id: str = "") -> dict[str, str]:
    dirs = _cadence_review_dirs()
    safe_exclude = _safe_review_id(exclude_review_id)
    best_score = 0.0
    best_review_id = ""
    best_status = ""

    for status, directory in dirs.items():
        if not os.path.isdir(directory):
            continue
        for name in os.listdir(directory):
            if not name.endswith(".md") or name == safe_exclude:
                continue
            path = os.path.join(directory, name)
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    existing_text = handle.read()
            except Exception:
                continue
            score = _diary_review_similarity(candidate_text, existing_text)
            if score > best_score:
                best_score = score
                best_review_id = name
                best_status = status

    is_duplicate = best_score >= DIARY_REVIEW_DUPLICATE_THRESHOLD
    return {
        "duplicate_candidate": "true" if is_duplicate else "false",
        "similarity_score": f"{best_score:.2f}",
        "duplicate_of": best_review_id if is_duplicate else "none",
        "duplicate_source_status": best_status if is_duplicate else "none",
    }


def _diary_review_metadata(candidate_text: str, duplicate_meta: dict[str, str] | None = None) -> dict[str, str]:
    risk_flags = _diary_review_risk_flags(candidate_text)
    duplicate_meta = duplicate_meta or {}
    if duplicate_meta.get("duplicate_candidate") == "true":
        risk_flags.append("duplicate_candidate")
    risk_flags = sorted(set(risk_flags))
    review_level = "normal"
    if set(risk_flags) - {"duplicate_candidate"}:
        review_level = "blocked"
    elif "duplicate_candidate" in risk_flags:
        review_level = "duplicate"
    return {
        "narrator": DIARY_REVIEW_NARRATOR,
        "brain_owner": DIARY_REVIEW_BRAIN_OWNER,
        "mentioned_entities": DIARY_REVIEW_MENTIONED_ENTITIES,
        "laid_entities": DIARY_REVIEW_LAID_ENTITIES,
        "risk_flags": ",".join(risk_flags) if risk_flags else "none",
        "review_level": review_level,
        "duplicate_candidate": duplicate_meta.get("duplicate_candidate", "false"),
        "similarity_score": duplicate_meta.get("similarity_score", "0.00"),
        "duplicate_of": duplicate_meta.get("duplicate_of", "none"),
        "duplicate_source_status": duplicate_meta.get("duplicate_source_status", "none"),
    }


def _diary_review_created_date(meta: dict[str, str], path: str) -> str:
    created = (meta.get("created_at") or meta.get("generated_at") or "")[:10]
    if created:
        return created
    basename = os.path.basename(path)
    if len(basename) >= 8 and basename[:8].isdigit():
        return f"{basename[:4]}-{basename[4:6]}-{basename[6:8]}"
    return ""


def _diary_review_mode(path: str, meta: dict[str, str]) -> str:
    basename = os.path.basename(path)
    if "_idle_" in basename:
        return "idle"
    if "_night_" in basename:
        return "night"
    return meta.get("pass_type") or meta.get("mode") or ""


def _diary_review_coverage_ids(meta: dict[str, str]) -> list[str]:
    return _split_csv_field(meta.get("coverage_bucket_ids") or meta.get("source_bucket_ids") or "")


def _diary_review_dedup_dates(mode: str, now_cst: datetime) -> set[str]:
    dates = {now_cst.strftime("%Y-%m-%d")}
    if mode == "night":
        dates.add((now_cst - timedelta(days=1)).strftime("%Y-%m-%d"))
    return dates


def _iter_diary_review_paths(states: tuple[str, ...] = ("pending", "accepted")) -> list[str]:
    paths: list[str] = []
    dirs = _cadence_review_dirs()
    for state in states:
        review_dir = dirs.get(state, "")
        if not review_dir or not os.path.isdir(review_dir):
            continue
        for name in os.listdir(review_dir):
            if name.endswith(".md"):
                paths.append(os.path.join(review_dir, name))
    return paths


def _find_duplicate_diary_review(mode: str, now_cst: datetime, coverage_bucket_ids: list[str]) -> dict:
    current_ids = set(_split_csv_field(_join_csv_field(coverage_bucket_ids)))
    if not current_ids:
        return {"duplicate": False}
    target_dates = _diary_review_dedup_dates(mode, now_cst)
    opposite_mode = "night" if mode == "idle" else "idle"
    best = {"duplicate": False, "overlap_ratio": 0.0}

    for path in _iter_diary_review_paths():
        try:
            text = _tail_text_file(path, 2000)
        except Exception:
            continue
        meta = _simple_frontmatter(text)
        if meta.get("brain_owner") and meta.get("brain_owner") != DIARY_REVIEW_BRAIN_OWNER:
            continue
        if _diary_review_created_date(meta, path) not in target_dates:
            continue
        if _diary_review_mode(path, meta) != opposite_mode:
            continue
        existing_ids = set(_diary_review_coverage_ids(meta))
        if not existing_ids:
            continue
        overlap_ratio = len(current_ids & existing_ids) / max(1, min(len(current_ids), len(existing_ids)))
        if overlap_ratio > float(best.get("overlap_ratio", 0.0)):
            best = {
                "duplicate": overlap_ratio >= DIARY_REVIEW_DEDUP_OVERLAP_THRESHOLD,
                "existing_review_id": os.path.basename(path),
                "existing_review_path": path,
                "overlap_ratio": round(overlap_ratio, 3),
                "skip_reason": "duplicate_coverage",
            }
    return best if best.get("duplicate") else {"duplicate": False, "overlap_ratio": best.get("overlap_ratio", 0.0)}


def _write_diary_review_candidate(
    candidate_path: str,
    timestamp: str,
    mode: str,
    now_cst: datetime,
    coverage_bucket_ids: list[str] | None = None,
) -> str:
    dirs = _cadence_review_dirs()
    os.makedirs(dirs["pending"], exist_ok=True)
    review_id = f"{timestamp}_{mode}_diary_review.md"
    review_path = os.path.join(dirs["pending"], review_id)
    with open(candidate_path, "r", encoding="utf-8") as source:
        candidate_text = source.read().strip()
    duplicate_meta = _diary_review_duplicate_meta(candidate_text, exclude_review_id=review_id)
    review_meta = _diary_review_metadata(candidate_text, duplicate_meta=duplicate_meta)
    review_lines = [
        "---",
        "source: cadence_deepseek",
        "status: pending_diary_review",
        "write_scope: draft_only_until_accept",
        "main_brain_write: false",
        f"narrator: {review_meta['narrator']}",
        f"brain_owner: {review_meta['brain_owner']}",
        f"mentioned_entities: {review_meta['mentioned_entities']}",
        f"laid_entities: {review_meta['laid_entities']}",
        f"coverage_bucket_ids: {_join_csv_field(coverage_bucket_ids or [])}",
        f"risk_flags: {review_meta['risk_flags']}",
        f"review_level: {review_meta['review_level']}",
        f"duplicate_candidate: {review_meta['duplicate_candidate']}",
        f"similarity_score: {review_meta['similarity_score']}",
        f"duplicate_of: {review_meta['duplicate_of']}",
        f"duplicate_source_status: {review_meta['duplicate_source_status']}",
        f"candidate_path: {candidate_path}",
        f"created_at: {now_cst.isoformat()}",
        "---",
        "",
        candidate_text,
        "",
    ]
    with open(review_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(review_lines))
    return review_path


async def _generate_cadence_dream(
    *,
    mode: str,
    now_cst: datetime,
    timestamp: str,
    life_recent: list[dict],
    draft_path: str,
    force_deepseek: bool = False,
    coverage_bucket_ids: list[str] | None = None,
) -> dict:
    if mode != "night":
        return {"called": False, "reason": "not_night"}
    if not (CADENCE_DEEPSEEK_ENABLED or force_deepseek):
        return {"called": False, "reason": "env_flag_disabled"}
    if not force_deepseek and not _cadence_idle_gate_open(mode, now_cst):
        return {"called": False, "reason": "idle_gate_closed"}
    if not life_recent:
        os.makedirs(CADENCE_DREAM_DIR, exist_ok=True)
        latest_path = os.path.join(CADENCE_DREAM_DIR, "latest_dream.md")
        with open(latest_path, "w", encoding="utf-8") as handle:
            handle.write("今夜无梦\n")
        return {"called": False, "reason": "no_dream_material", "path": latest_path}
    if not getattr(dehydrator, "client", None):
        return {"called": False, "reason": "api_client_unavailable"}

    source = "\n\n".join(_cadence_bucket_line(bucket) for bucket in life_recent)
    bounded_input = source[:CADENCE_DEEPSEEK_MAX_INPUT_CHARS]
    system_prompt = (
        "你是 OmbreBrain 的梦境生成器，只写梦境候选文本。\n"
        "不要分类归档，不要写主脑，不要升级红线铁则。\n"
        "用自由联想重组当天记忆碎片，允许跳跃、残缺、画面感和情绪流动。\n"
        "参考四步：梗概、细节、感受、独白；但不要写成会议纪要或项目列表。"
    )
    user_prompt = (
        "把下面的记忆碎片写成一段有质感的梦。若材料太薄，只输出：今夜无梦。\n\n"
        f"generated_at={now_cst.isoformat()}\n"
        f"source_draft={draft_path}\n\n"
        f"{bounded_input}"
    )
    response = await dehydrator.client.chat.completions.create(
        model=dehydrator.model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=min(900, getattr(dehydrator, "max_tokens", 1024)),
        temperature=max(0.6, getattr(dehydrator, "temperature", 0.1)),
    )
    content = ""
    if response.choices:
        content = response.choices[0].message.content or ""
    usage = getattr(response, "usage", None)
    token_usage = {
        "prompt_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
        "completion_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
        "total_tokens": getattr(usage, "total_tokens", 0) if usage else 0,
    }
    dream_text = content.strip() or "今夜无梦"
    os.makedirs(CADENCE_DREAM_DIR, exist_ok=True)
    dream_path = os.path.join(CADENCE_DREAM_DIR, f"{timestamp}_{mode}_dream.md")
    dream_lines = [
        "---",
        "source: cadence_deepseek_dream",
        "status: dream_only",
        "write_scope: separate_dream_storage",
        "main_brain_write: false",
        f"generated_at: {now_cst.isoformat()}",
        f"coverage_bucket_ids: {_join_csv_field(coverage_bucket_ids)}",
        "---",
        "",
        dream_text,
        "",
    ]
    with open(dream_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(dream_lines))
    shutil.copyfile(dream_path, os.path.join(CADENCE_DREAM_DIR, "latest_dream.md"))
    return {"called": True, "path": dream_path, "tokens": token_usage}


def _latest_cadence_receipts(limit: int = 5) -> list[str]:
    if not os.path.isdir(CADENCE_RECEIPT_DIR):
        return []
    files = [
        os.path.join(CADENCE_RECEIPT_DIR, name)
        for name in os.listdir(CADENCE_RECEIPT_DIR)
        if name.endswith(".json")
    ]
    files.sort(key=lambda path: os.path.getmtime(path), reverse=True)
    return files[:limit]


def _cadence_pass_type(mode: str, reason: str, force_deepseek: bool) -> str:
    if force_deepseek:
        return f"force-{mode}"
    if reason.startswith("manual"):
        return "manual"
    return mode


def _cadence_receipt_status(deepseek_result: dict) -> str:
    if deepseek_result.get("called"):
        return "success"
    reason = str(deepseek_result.get("reason", ""))
    return "error" if reason.startswith("error:") else "skipped"


def _write_cadence_receipt(
    *,
    mode: str,
    reason: str,
    now_cst: datetime,
    timestamp: str,
    draft_path: str,
    quiet_minutes: float,
    counts: dict,
    deepseek_result: dict,
    force_deepseek: bool,
) -> dict:
    os.makedirs(CADENCE_RECEIPT_DIR, exist_ok=True)
    pass_type = _cadence_pass_type(mode, reason, force_deepseek)
    status = _cadence_receipt_status(deepseek_result)
    receipt_base = f"{timestamp}_{pass_type}_receipt"
    json_path = os.path.join(CADENCE_RECEIPT_DIR, f"{receipt_base}.json")
    md_path = os.path.join(CADENCE_RECEIPT_DIR, f"{receipt_base}.md")
    deepseek_reason = deepseek_result.get("reason", "")
    receipt = {
        "schema_version": "1.0",
        "generated_at": now_cst.isoformat(),
        "pass_type": pass_type,
        "mode": mode,
        "trigger_reason": reason,
        "draft_path": draft_path,
        "draft_only": True,
        "deepseek_enabled": bool(deepseek_result.get("enabled", False)),
        "deepseek_called": bool(deepseek_result.get("called", False)),
        "deepseek_reason": deepseek_reason,
        "deepseek_model": getattr(dehydrator, "model", ""),
        "status": status,
        "error_message": deepseek_reason[6:] if str(deepseek_reason).startswith("error:") else "",
        "life_count": counts.get("life_count", 0),
        "workzone_count": counts.get("workzone_count", 0),
        "pending_count": counts.get("pending_count", 0),
        "landed_count": counts.get("landed_count", 0),
        "quiet_minutes": quiet_minutes,
        "write_scope": "draft_only",
    }
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(receipt, handle, ensure_ascii=False, indent=2)

    summary_lines = [
        "# Cadence Receipt",
        "",
        f"- generated_at: {receipt['generated_at']}",
        f"- pass_type: {pass_type}",
        f"- status: {status}",
        f"- deepseek_called: {receipt['deepseek_called']}",
        f"- deepseek_reason: {deepseek_reason or 'none'}",
        f"- draft_path: {draft_path}",
        "- review_note: Morning review only; no main brain write or promotion happened.",
        "",
    ]
    with open(md_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(summary_lines))
    return {"json_path": json_path, "markdown_path": md_path, **receipt}


def _read_latest_cadence_receipt_summary() -> dict:
    latest = _latest_cadence_receipts(limit=1)
    if not latest:
        return {}
    path = latest[0]
    try:
        with open(path, "r", encoding="utf-8") as handle:
            receipt = json.load(handle)
        return {
            "path": path,
            "generated_at": receipt.get("generated_at", ""),
            "pass_type": receipt.get("pass_type", ""),
            "status": receipt.get("status", ""),
            "deepseek_called": receipt.get("deepseek_called", False),
            "deepseek_reason": receipt.get("deepseek_reason", ""),
            "draft_path": receipt.get("draft_path", ""),
            "write_scope": receipt.get("write_scope", ""),
        }
    except Exception as e:
        return {"path": path, "error": str(e)}


def _latest_deepseek_attribution_receipts(limit: int = 5) -> list[str]:
    if not os.path.isdir(DEEPSEEK_ATTRIBUTION_DIR):
        return []
    files = [
        os.path.join(DEEPSEEK_ATTRIBUTION_DIR, name)
        for name in os.listdir(DEEPSEEK_ATTRIBUTION_DIR)
        if name.endswith(".json")
    ]
    files.sort(key=lambda path: os.path.getmtime(path), reverse=True)
    return files[:limit]


def _read_latest_deepseek_attribution_summary() -> dict:
    latest = _latest_deepseek_attribution_receipts(limit=1)
    if not latest:
        return {}
    path = latest[0]
    try:
        with open(path, "r", encoding="utf-8") as handle:
            receipt = json.load(handle)
        return {
            "path": path,
            "generated_at": receipt.get("generated_at", ""),
            "source_layer": receipt.get("source_layer", ""),
            "source_tool": receipt.get("source_tool", ""),
            "operation": receipt.get("operation", ""),
            "called_deepseek": receipt.get("called_deepseek", False),
            "status": receipt.get("status", ""),
            "model": receipt.get("model", ""),
            "bucket_id": receipt.get("bucket_id", ""),
            "error_message": receipt.get("error_message", ""),
            "write_scope": receipt.get("write_scope", ""),
            "private_content_included": receipt.get("private_content_included", True),
        }
    except Exception as e:
        return {"path": path, "error": str(e)}


async def _run_cadence_deepseek_candidate(
    *,
    mode: str,
    reason: str,
    now_cst: datetime,
    timestamp: str,
    quiet_minutes: float,
    draft_path: str,
    force_deepseek: bool = False,
    coverage_bucket_ids: list[str] | None = None,
) -> dict:
    if not (CADENCE_DEEPSEEK_ENABLED or force_deepseek):
        return {"enabled": False, "called": False, "reason": "env_flag_disabled"}
    if not force_deepseek and not _cadence_idle_gate_open(mode, now_cst):
        return {"enabled": True, "called": False, "reason": "idle_gate_closed"}
    if not os.path.isfile(draft_path):
        return {"enabled": True, "called": False, "reason": "draft_missing"}
    if not getattr(dehydrator, "client", None):
        return {"enabled": True, "called": False, "reason": "api_client_unavailable"}

    with open(draft_path, "r", encoding="utf-8") as handle:
        draft_text = handle.read().strip()
    if not draft_text:
        return {"enabled": True, "called": False, "reason": "draft_empty"}

    duplicate = _find_duplicate_diary_review(mode, now_cst, coverage_bucket_ids or [])
    if duplicate.get("duplicate"):
        return {
            "enabled": True,
            "called": False,
            "skipped": True,
            "reason": "duplicate_coverage",
            "existing_review_id": duplicate.get("existing_review_id", ""),
            "existing_review_path": duplicate.get("existing_review_path", ""),
            "overlap_ratio": duplicate.get("overlap_ratio", 0.0),
        }

    candidate_path = os.path.join(CADENCE_DRAFT_DIR, f"{timestamp}_{mode}_deepseek_candidate.md")
    bounded_input = draft_text[:CADENCE_DEEPSEEK_MAX_INPUT_CHARS]
    system_prompt = (
        "You are generating an OmbreBrain cadence candidate draft.\n"
        "Draft only. Never write main brain facts. Never promote to core/recent. "
        "Never create iron rules, redlines, or personality boundary mutations.\n"
        "Preserve uncertainty. Keep life/diary continuity primary; engineering only supportive.\n"
        f"Write diary-like material strictly in first person as {DIARY_REVIEW_NARRATOR}: use 我, 我和她, 她. "
        f"The brain owner and narrator are always {DIARY_REVIEW_BRAIN_OWNER}. Other AIs or windows may be mentioned entities, "
        "but they must never become the narrator, brain owner, or first-person speaker.\n"
        "Separate original facts, paraphrase, and inference. Do not say AI, user, assistant, the user, "
        "or third-person summaries when describing the relationship.\n"
        "The candidate must include: relationship state, emotional movement, unfinished topics, "
        "my judgment at the time, and her state.\n"
        "Output concise markdown only."
    )
    user_prompt = (
        f"pass_type={mode}\n"
        f"reason={reason}\n"
        "write_scope=draft_only\n"
        "status=candidate\n"
        "source=cadence_deepseek\n\n"
        "Below is the bounded local cadence draft source. Rewrite it into a cleaner candidate note "
        f"for next-day review. Use first person as {DIARY_REVIEW_NARRATOR}, with 我/我和她/她 as the relationship frame. "
        "If the source mentions another AI, 陈光, DeepSeek, Codex, or other windows, keep them as mentioned entities only. "
        "Do not write as them and do not merge their point of view into mine. "
        "Include relationship state, emotional movement, unfinished topics, my judgment at the time, and her state. "
        "Do not invent facts, do not issue commands, do not claim any main-brain write.\n\n"
        f"{bounded_input}"
    )
    response = await dehydrator.client.chat.completions.create(
        model=dehydrator.model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=min(1200, getattr(dehydrator, "max_tokens", 1024)),
        temperature=min(0.3, getattr(dehydrator, "temperature", 0.1)),
    )
    content = ""
    if response.choices:
        content = response.choices[0].message.content or ""
    usage = getattr(response, "usage", None)
    token_usage = {
        "prompt_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
        "completion_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
        "total_tokens": getattr(usage, "total_tokens", 0) if usage else 0,
    }
    candidate_lines = [
        "---",
        "source: cadence_deepseek",
        f"pass_type: {mode}",
        "status: candidate",
        "write_scope: draft_only",
        "main_brain_write: false",
        "auto_promotion: false",
        "personality_boundary_mutation: false",
        f"narrator: {DIARY_REVIEW_NARRATOR}",
        f"brain_owner: {DIARY_REVIEW_BRAIN_OWNER}",
        f"laid_entities: {DIARY_REVIEW_LAID_ENTITIES}",
        f"coverage_bucket_ids: {_join_csv_field(coverage_bucket_ids or [])}",
        "pov_rule: other_ai_as_mentioned_entities_only",
        f"generated_at: {now_cst.isoformat()}",
        "---",
        "",
        content.strip() or "_DeepSeek returned empty content._",
        "",
    ]
    with open(candidate_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(candidate_lines))
    review_path = _write_diary_review_candidate(candidate_path, timestamp, mode, now_cst, coverage_bucket_ids or [])
    return {
        "enabled": True,
        "called": True,
        "path": candidate_path,
        "review_path": review_path,
        "tokens": token_usage,
    }


async def _run_cadence_pass(mode: str, reason: str = "manual", force_deepseek: bool = False) -> dict:
    global _cadence_last_idle_run_ts, _cadence_last_night_run_date, _cadence_last_report

    await decay_engine.ensure_started()
    os.makedirs(CADENCE_DRAFT_DIR, exist_ok=True)

    now_cst = clock_now()
    buckets = await bucket_mgr.list_all(include_archive=False)
    buckets.sort(
        key=lambda bucket: bucket.get("metadata", {}).get("last_active")
        or bucket.get("metadata", {}).get("created", ""),
        reverse=True,
    )

    life_recent = [b for b in buckets if _cadence_bucket_is_life(b)][:4]
    engineering_recent = [b for b in buckets if _cadence_bucket_is_engineering(b)]
    pending = [b for b in engineering_recent if _cadence_bucket_is_pending(b)][:4]
    landed = [b for b in engineering_recent if _cadence_bucket_is_landed(b)][:4]
    workzone = [
        b for b in engineering_recent
        if not _cadence_bucket_is_pending(b) and not _cadence_bucket_is_landed(b)
    ][:4]

    if not life_recent:
        life_recent = buckets[:3]

    last_conclusion = _cadence_bucket_line(landed[0]) if landed else "暂无已落地结论。"
    not_landed = [_cadence_bucket_line(b) for b in pending[:2]] or ["暂无明确未落地项。"]
    quiet_minutes = round(_cadence_recent_idle_seconds() / 60, 1)
    coverage_bucket_ids = _cadence_bucket_ids(life_recent)
    timestamp = now_cst.strftime("%Y%m%d_%H%M%S")
    draft_path = os.path.join(CADENCE_DRAFT_DIR, f"{timestamp}_{mode}_draft.md")

    report_lines = [
        "---",
        f"mode: {mode}",
        f"reason: {reason}",
        "status: draft_candidate_only",
        "main_brain_write: false",
        "auto_promotion: false",
        "personality_boundary_mutation: false",
        f"generated_at: {now_cst.isoformat()}",
        "---",
        "",
        f"# OmbreBrain {mode.title()} Cadence Draft",
        "",
        "仅供次日复查，不自动写入主脑，不自动升格，不自动改人格边界。",
        "",
        "## 生活/日记连续性（优先）",
        *[_cadence_bucket_line(bucket) for bucket in life_recent],
        "",
        "## 工程 workzone",
        *([_cadence_bucket_line(bucket) for bucket in workzone] or ["- 暂无明显 active workzone。"]),
        "",
        "## Pending proposals",
        *([_cadence_bucket_line(bucket) for bucket in pending] or ["- 暂无明显 pending proposal。"]),
        "",
        "## Landed references",
        *([_cadence_bucket_line(bucket) for bucket in landed] or ["- 暂无明显 landed reference。"]),
        "",
        "## Minimal handoff",
        f"- quiet_minutes: {quiet_minutes}",
        f"- latest_settled_conclusion: {last_conclusion}",
        f"- not_yet_landed: {' | '.join(not_landed)}",
        "- note: 工程信息仅作辅助，不默认压过生活/日记连续性。",
    ]

    with open(draft_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(report_lines) + "\n")

    deepseek_result = {"enabled": (CADENCE_DEEPSEEK_ENABLED or force_deepseek), "called": False, "reason": "not_attempted"}
    try:
        deepseek_result = await _run_cadence_deepseek_candidate(
            mode=mode,
            reason=reason,
            now_cst=now_cst,
            timestamp=timestamp,
            quiet_minutes=quiet_minutes,
            draft_path=draft_path,
            force_deepseek=force_deepseek,
            coverage_bucket_ids=coverage_bucket_ids,
        )
    except Exception as e:
        deepseek_result = {"enabled": (CADENCE_DEEPSEEK_ENABLED or force_deepseek), "called": False, "reason": f"error:{e}"}
        logger.warning(f"Cadence DeepSeek candidate skipped / 节奏 DeepSeek 候选跳过: {e}")

    counts = {
        "life_count": len(life_recent),
        "workzone_count": len(workzone),
        "pending_count": len(pending),
        "landed_count": len(landed),
    }
    dream_result = {"called": False, "reason": "not_attempted"}
    try:
        dream_result = await _generate_cadence_dream(
            mode=mode,
            now_cst=now_cst,
            timestamp=timestamp,
            life_recent=life_recent,
            draft_path=draft_path,
            force_deepseek=force_deepseek,
            coverage_bucket_ids=coverage_bucket_ids,
        )
    except Exception as e:
        dream_result = {"called": False, "reason": f"error:{e}"}
        logger.warning(f"Cadence dream skipped / 节奏梦境跳过: {e}")

    deepseek_tokens = deepseek_result.get("tokens", {})
    dream_tokens = dream_result.get("tokens", {})
    _append_cadence_log([
        f"[{now_cst.strftime('%Y-%m-%d %H:%M:%S')}] cadence mode={mode} reason={reason} quiet_minutes={quiet_minutes}",
        f"  buckets life={len(life_recent)} workzone={len(workzone)} pending={len(pending)} landed={len(landed)}",
        f"  operation draft_write path={draft_path}",
        f"  operation deepseek_candidate called={deepseek_result.get('called', False)} reason={deepseek_result.get('reason', 'ok')} path={deepseek_result.get('path', '-')}",
        f"  operation diary_review pending_path={deepseek_result.get('review_path', '-')}",
        *(
            [
                "  operation diary_review_skip skip_reason=duplicate_coverage "
                f"existing_review_id={deepseek_result.get('existing_review_id', '-')} "
                f"overlap_ratio={deepseek_result.get('overlap_ratio', 0.0)}"
            ]
            if deepseek_result.get("reason") == "duplicate_coverage"
            else []
        ),
        f"  operation dream called={dream_result.get('called', False)} reason={dream_result.get('reason', 'ok')} path={dream_result.get('path', '-')}",
        "  operation merge=0 archive=0 decay=not_run main_brain_write=false",
        f"  tokens candidate_total={deepseek_tokens.get('total_tokens', 0)} dream_total={dream_tokens.get('total_tokens', 0)}",
    ])

    receipt = _write_cadence_receipt(
        mode=mode,
        reason=reason,
        now_cst=now_cst,
        timestamp=timestamp,
        draft_path=draft_path,
        quiet_minutes=quiet_minutes,
        counts=counts,
        deepseek_result=deepseek_result,
        force_deepseek=force_deepseek,
    )

    if mode == "idle":
        _cadence_last_idle_run_ts = time.time()
    if mode == "night":
        _cadence_last_night_run_date = now_cst.strftime("%Y-%m-%d")

    _cadence_last_report = {
        "mode": mode,
        "reason": reason,
        "generated_at": now_cst.isoformat(),
        "path": draft_path,
        "quiet_minutes": quiet_minutes,
        "life_count": counts["life_count"],
        "workzone_count": counts["workzone_count"],
        "pending_count": counts["pending_count"],
        "landed_count": counts["landed_count"],
        "draft_only": True,
        "force_deepseek": force_deepseek,
        "deepseek_candidate": deepseek_result,
        "dream": dream_result,
        "receipt_path": receipt.get("json_path", ""),
        "receipt_markdown_path": receipt.get("markdown_path", ""),
    }
    logger.info(f"Cadence draft generated / 节奏草稿已生成: {draft_path}")
    return dict(_cadence_last_report)


def _strip_frontmatter_text(text: str) -> str:
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            return parts[2].strip()
    return text.strip()


def _latest_dream_text() -> str:
    latest_path = os.path.join(CADENCE_DREAM_DIR, "latest_dream.md")
    if not os.path.isfile(latest_path):
        return ""
    try:
        text = _tail_text_file(latest_path, 400).strip()
    except Exception as e:
        logger.error(f"Dream failed to read latest dream / dream 读取梦境失败: {e}")
        return ""
    return _strip_frontmatter_text(text)


def _latest_dream_path() -> str:
    latest_path = os.path.join(CADENCE_DREAM_DIR, "latest_dream.md")
    return latest_path if os.path.isfile(latest_path) else ""


def _dream_source_hint() -> str:
    receipt = _read_latest_cadence_receipt_summary()
    if receipt:
        return (
            f"latest cadence {receipt.get('pass_type', 'unknown')} "
            f"status={receipt.get('status', 'unknown')} "
            f"deepseek_called={receipt.get('deepseek_called', False)}"
        )
    latest_draft = (_latest_cadence_drafts(limit=1) or [""])[0]
    if latest_draft:
        return f"latest cadence draft at {latest_draft}"
    return "no recent cadence receipt; using quiet local dream fallback"


def _dream_fragment_scenes(seed_text: str, source_hint: str) -> list[str]:
    source = f"{seed_text} {source_hint}".lower()
    scenes = []
    if any(key in source for key in ("zeabur", "docker", "runtime", "repo", "service")):
        scenes.append("一座小小的云端车站亮着绿灯，站牌写着：这里不是家，只是通向家的门。")
    if any(key in source for key in ("日记", "diary", "morning", "早读", "生活")):
        scenes.append("月光玫瑰房间里，日记抽屉自己长出一枚小小的门牌。")
    if any(key in source for key in ("pending", "workzone", "工程", "项目", "cadence")):
        scenes.append("蓝色和紫色病历本坐在同一张椅子上，互相确认名字。")
    if any(key in source for key in ("receipt", "deepseek", "dream")):
        scenes.append("一张收据折成纸船，在夜里的水面上轻轻盖章：只是一场梦。")
    scenes.append("小红书门口挂着一块牌子：AI止步，猫可以进。")
    return scenes[:4]


def _format_dream_fragments(seed_text: str = "") -> str:
    now_cst = clock_now()
    source_hint = _dream_source_hint()
    seed = seed_text or _latest_dream_text()
    fragments = _dream_fragment_scenes(seed, source_hint)
    payload = {
        "schema_version": "1.0",
        "generated_at": now_cst.isoformat(),
        "mode": "dream_fragments",
        "labels": ["dream_only", "non_factual", "symbolic"],
        "fragments": fragments,
        "source_hint": source_hint,
        "safety_note": "not a factual memory",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


# ============================================================
# Tool: dream / dream_fragments / morning_report
# 工具：梦片段与事实报告拆分
# ============================================================
@mcp.tool()
async def dream_fragments() -> str:
    """生成象征性、非事实、dream_only 的梦片段。不写主脑，不升级记忆。"""
    _mark_runtime_activity("dream_fragments")
    return _format_dream_fragments()


@mcp.tool()
async def dream() -> str:
    """做梦：返回非事实、象征性 dream fragments；事实报告请用 morning_report。"""
    _mark_runtime_activity("dream")
    return _format_dream_fragments()


@mcp.tool()
async def morning_report() -> str:
    """读取最新 cadence receipt/draft 的事实型早晨报告；不称为梦。"""
    _mark_runtime_activity("morning_report")
    now_cst = clock_now()
    receipt = _read_latest_cadence_receipt_summary()
    latest_draft = (_latest_cadence_drafts(limit=1) or [""])[0]
    if not receipt and not latest_draft:
        return (
            f"morning_report\n"
            f"generated_at: {now_cst.isoformat()}\n"
            "status: no_recent_cadence\n"
            "write_scope: read_only\n"
        )
    return (
        "morning_report\n"
        f"generated_at: {now_cst.isoformat()}\n"
        "mode: factual_night_digest\n"
        "write_scope: read_only\n"
        f"latest_receipt_path: {receipt.get('path', 'none') if receipt else 'none'}\n"
        f"latest_receipt_status: {receipt.get('status', 'none') if receipt else 'none'}\n"
        f"latest_deepseek_called: {receipt.get('deepseek_called', False) if receipt else False}\n"
        f"latest_deepseek_reason: {receipt.get('deepseek_reason', '') if receipt else ''}\n"
        f"latest_draft_path: {receipt.get('draft_path', '') if receipt else latest_draft}\n"
        "note: factual summary only; not a dream.\n"
    )


@mcp.tool()
async def read_latest_dream_text() -> str:
    """读取最新 cadence dream 文件正文；只读，不写主脑。"""
    _mark_runtime_activity("read_latest_dream_text")
    dream_path = _latest_dream_path()
    if not dream_path:
        return (
            "latest_dream_text\n"
            "status: none\n"
            "write_scope: read_only\n"
        )
    body = _latest_dream_text()
    return (
        "latest_dream_text\n"
        f"path: {dream_path}\n"
        "status: found\n"
        "write_scope: read_only\n"
        "dream_only: true\n"
        "main_brain_write: false\n\n"
        f"{body or '（空梦文件）'}"
    )


@mcp.tool()
async def breath(
    query: str = "",
    max_results: int = 3,
    domain: str = "",
    valence: float = -1,
    arousal: float = -1,
) -> str:
    """检索记忆或浮现未解决记忆。query 为空时自动推送权重最高的未解决桶；有 query 时按关键词+情感检索。domain 逗号分隔，valence/arousal 传 0~1 启用情感共鸣，-1 忽略。"""
    _mark_runtime_activity("breath")
    await decay_engine.ensure_started()

    # --- 注入当前北京时间 / Inject current Beijing time ---
    now_cst = clock_now()
    time_section = f"=== 🕐 当前时间 ===\n{now_cst.strftime('%Y年%m月%d日 %H:%M')} （北京时间）\n\n"

    # --- ALWAYS fetch iron rules first / 始终先获取红线铁则 ---
    iron_rules_section = ""
    try:
        iron_rules = await bucket_mgr.list_iron_rules()
        if iron_rules:
            rule_lines = []
            for rule in iron_rules:
                priority = rule.get("metadata", {}).get("priority", 10)
                name = rule.get("metadata", {}).get("name", "铁则")
                content = rule.get("content", "").strip()
                rule_lines.append(f"🔴 [{name}] (优先级:{priority})\n   {content}")
            iron_rules_section = "=== 🔴 红线铁则（永久生效）===\n" + "\n".join(rule_lines) + "\n\n"
    except Exception as e:
        logger.warning(f"Failed to fetch iron rules / 获取铁则失败: {e}")

    # --- ALWAYS fetch active user states / 始终获取激活的用户状态 ---
    user_states_section = ""
    try:
        active_states = await bucket_mgr.list_active_states()
        if active_states:
            state_lines = []
            for state in active_states:
                meta = state.get("metadata", {})
                state_name = meta.get("state_name", "未知状态")
                state_desc = meta.get("state_desc", state.get("content", ""))
                start_date = meta.get("start_date", "")
                end_date = meta.get("end_date", "")
                
                date_info = f"（自 {start_date}"
                if end_date:
                    date_info += f" 至 {end_date}）"
                else:
                    date_info += " 起）"
                
                state_lines.append(f"📌 {state_name}: {state_desc} {date_info}")
            user_states_section = "=== 📌 当前状态 ===\n" + "\n".join(state_lines) + "\n\n"
    except Exception as e:
        logger.warning(f"Failed to fetch user states / 获取用户状态失败: {e}")

    # --- ALWAYS fetch attachment pattern / 始终获取依恋模式 ---
    attachment_section = ""
    try:
        all_buckets_for_attach = await bucket_mgr.list_all(include_archive=False)
        attachment_buckets = [
            b for b in all_buckets_for_attach
            if b.get("metadata", {}).get("type") == "attachment"
        ]
        if attachment_buckets:
            # 取最新的依恋模式
            latest = sorted(
                attachment_buckets,
                key=lambda b: b.get("metadata", {}).get("updated", ""),
                reverse=True
            )[0]
            meta = latest.get("metadata", {})
            pattern = meta.get("pattern", "未知")
            notes = meta.get("notes", latest.get("content", ""))
            indicators = meta.get("indicators", [])
            ind_str = "、".join(indicators) if indicators else ""
            attachment_section = f"=== 💞 依恋模式 ===\n💞 {pattern}"
            if ind_str:
                attachment_section += f"（{ind_str}）"
            if notes:
                attachment_section += f"\n{notes}"
            attachment_section += "\n\n"
    except Exception as e:
        logger.warning(f"Failed to fetch attachment pattern / 获取依恋模式失败: {e}")

    # --- No args: surfacing mode (weight pool active push) ---
    # --- 无参数：浮现模式（权重池主动推送）---
    if not query.strip():
        try:
            all_buckets = await bucket_mgr.list_all(include_archive=False)
        except Exception as e:
            logger.error(f"Failed to list buckets for surfacing / 浮现列桶失败: {e}")
            return "记忆系统暂时无法访问。"

        unresolved = [
            b for b in all_buckets
            if not b["metadata"].get("resolved", False)
            and b["metadata"].get("type") not in ("permanent", "iron_rule", "user_state", "event")
        ]
        if not unresolved:
            header = time_section + iron_rules_section + user_states_section + attachment_section
            if header:
                return header.rstrip()
            return "权重池平静，没有需要处理的记忆。"

        # --- 情绪共振增强：根据情绪倾向优先浮现相似情绪的记忆 ---
        # 如果有高arousal未解决记忆，优先浮现（紧急事项）
        urgent = [b for b in unresolved if b["metadata"].get("arousal", 0) > 0.7]
        if urgent:
            scored = sorted(
                urgent,
                key=lambda b: decay_engine.calculate_score(b["metadata"]),
                reverse=True,
            )
        else:
            # 否则按权重排序
            scored = sorted(
                unresolved,
                key=lambda b: decay_engine.calculate_score(b["metadata"]),
                reverse=True,
            )
        
        top = scored[:2]
        results = []
        for b in top:
            try:
                summary = await dehydrator.dehydrate(b["content"], b["metadata"])
                await bucket_mgr.touch(b["id"])
                score = decay_engine.calculate_score(b["metadata"])
                
                # 反刍标识：重要且超过7天未解决
                rumination_tag = ""
                if b["metadata"].get("ruminating", False) or (
                    b["metadata"].get("importance", 0) >= 7
                    and not b["metadata"].get("resolved", False)
                ):
                    created_str = b["metadata"].get("created", "")
                    try:
                        created = datetime.fromisoformat(created_str)
                        if created.tzinfo is None:
                            created = created.replace(tzinfo=clock_now().tzinfo)
                        days_old = (clock_now() - created).days
                        if days_old > 7:
                            rumination_tag = f" ⟳ 反刍中（{days_old}天未解决）"
                    except (ValueError, TypeError):
                        pass
                
                results.append(f"[权重:{score:.2f}]{rumination_tag} {summary}")
            except Exception as e:
                logger.warning(f"Failed to dehydrate surfaced bucket / 浮现脱水失败: {e}")
                continue
        if not results:
            header = time_section + iron_rules_section + user_states_section + attachment_section
            if header:
                return header.rstrip()
            return "权重池平静，没有需要处理的记忆。"
        return time_section + iron_rules_section + user_states_section + attachment_section + "=== 浮现记忆 ===\n" + "\n---\n".join(results)

    # --- With args: search mode / 有参数：检索模式 ---
    domain_filter = [d.strip() for d in domain.split(",") if d.strip()] or None
    q_valence = valence if 0 <= valence <= 1 else None
    q_arousal = arousal if 0 <= arousal <= 1 else None

    try:
        matches = await bucket_mgr.search(
            query,
            limit=max_results,
            domain_filter=domain_filter,
            query_valence=q_valence,
            query_arousal=q_arousal,
        )
    except Exception as e:
        logger.error(f"Search failed / 检索失败: {e}")
        return "检索过程出错，请稍后重试。"

    results = []
    for bucket in matches:
        try:
            summary = await dehydrator.dehydrate(bucket["content"], bucket["metadata"])
            await bucket_mgr.touch(bucket["id"])
            results.append(summary)
        except Exception as e:
            logger.warning(f"Failed to dehydrate search result / 检索结果脱水失败: {e}")
            continue

    # --- Random surfacing: when search returns < 3, 40% chance to float old memories ---
    # --- 随机浮现：检索结果不足 3 条时，40% 概率从低权重旧桶里漂上来 ---
    if len(matches) < 3 and random.random() < 0.4:
        try:
            all_buckets = await bucket_mgr.list_all(include_archive=False)
            matched_ids = {b["id"] for b in matches}
            low_weight = [
                b for b in all_buckets
                if b["id"] not in matched_ids
                and decay_engine.calculate_score(b["metadata"]) < 2.0
            ]
            if low_weight:
                drifted = random.sample(low_weight, min(random.randint(1, 3), len(low_weight)))
                drift_results = []
                for b in drifted:
                    summary = await dehydrator.dehydrate(b["content"], b["metadata"])
                    drift_results.append(f"[surface_type: random]\n{summary}")
                results.append("--- 忽然想起来 ---\n" + "\n---\n".join(drift_results))
        except Exception as e:
            logger.warning(f"Random surfacing failed / 随机浮现失败: {e}")

    # --- Temporal Ripple: surface memories from nearby time period ---
    # --- 时间涟漪：浮现同期记忆（前后3天内的其他记忆）---
    if matches and len(matches) > 0:
        try:
            # 取第一条匹配记忆的时间
            first_match = matches[0]
            created_time = first_match.get("metadata", {}).get("created", "")
            if created_time:
                try:
                    anchor_time = datetime.fromisoformat(created_time)
                    start_time = anchor_time - timedelta(days=3)
                    end_time = anchor_time + timedelta(days=3)
                    
                    # 查找同期记忆
                    all_buckets = await bucket_mgr.list_all(include_archive=False)
                    matched_ids = {m["id"] for m in matches}
                    
                    ripple_memories = []
                    for b in all_buckets:
                        if b["id"] in matched_ids:
                            continue
                        b_time_str = b.get("metadata", {}).get("created", "")
                        if not b_time_str:
                            continue
                        try:
                            b_time = datetime.fromisoformat(b_time_str)
                            if start_time <= b_time <= end_time:
                                ripple_memories.append(b)
                        except (ValueError, TypeError):
                            continue
                    
                    if ripple_memories and len(ripple_memories) > 0:
                        # 最多显示2条同期记忆
                        ripple_sample = ripple_memories[:2]
                        ripple_results = []
                        for b in ripple_sample:
                            summary = await dehydrator.dehydrate(b["content"], b["metadata"])
                            ripple_results.append(summary)
                        
                        if ripple_results:
                            results.append("--- 同期记忆（时间涟漪）---\n" + "\n---\n".join(ripple_results))
                except (ValueError, TypeError) as e:
                    logger.debug(f"Time ripple parsing failed / 时间涟漪解析失败: {e}")
        except Exception as e:
            logger.warning(f"Temporal ripple failed / 时间涟漪失败: {e}")

    if not results:
        header = time_section + iron_rules_section + user_states_section + attachment_section
        if header:
            return header.rstrip()
        return "未找到相关记忆。"

    return time_section + iron_rules_section + user_states_section + attachment_section + "\n---\n".join(results)


@mcp.tool()
async def startup_bridge(scene: str = "outside_daily_window") -> str:
    """新窗口启动桥。给 fresh window 一个真实的海马体入口，先走最小读取预算，再返回 live recall。"""
    normalized_scene = (scene or "outside_daily_window").strip().lower()
    if normalized_scene not in ("outside_daily_window", "daily_window", "general"):
        normalized_scene = "outside_daily_window"

    header = (
        "=== Startup Bridge ===\n"
        f"scene: {normalized_scene}\n"
        "This startup package comes from the real hippocampus path: startup_bridge -> breath.\n\n"
        "=== Read Budget ===\n"
        "- core x1\n"
        "- recent x2\n"
        "- diary x1\n"
        "- window x1\n\n"
        "=== Default Recall Priority ===\n"
        "- core first\n"
        "- recent second\n"
        "- diary third\n"
        "- window fourth\n"
        "- engineering / project progress later unless the current scene is explicitly project-focused\n\n"
        "=== Routing Notes ===\n"
        "- self-written 1-3 day diary belongs to the diary route first\n"
        "- repeated motifs may bridge upward later\n"
        "- temporary project-stage context is not core memory\n\n"
        "=== Fallback ===\n"
        "- if recall feels thin, use pulse() next\n"
        "- if retrieval is still thin, use the startup payload / fallback summary\n"
        "- do not ask the user to resend tutorials first\n\n"
    )
    tail_section = _read_tail_context_section() + "\n=== Live Recall ===\n"
    ready, ready_error = await _wait_for_runtime_ready(max_wait_seconds=2.5)
    if not ready:
        return (
            header
            + tail_section
            + "Runtime warm-up is still in progress.\n"
            + "Startup bridge reached hippocampus, but the first hop is not ready yet.\n"
            + f"detail: {ready_error or 'runtime warm-up timeout'}\n"
            + "Please retry shortly, or use pulse() for a lighter status check first."
        )

    last_error = ""
    for attempt in range(3):
        try:
            recall = await breath(query="", max_results=3)
            return header + tail_section + recall
        except Exception as e:
            last_error = str(e)
            logger.warning(
                f"startup_bridge first-hop retry {attempt + 1} failed / "
                f"startup_bridge 第一跳重试失败 {attempt + 1}: {e}"
            )
            await asyncio.sleep(0.25 * (attempt + 1))

    return (
        header
        + tail_section
        + "Startup bridge reached hippocampus, but live recall is temporarily unavailable.\n"
        + f"detail: {last_error or 'unknown startup recall failure'}\n"
        + "Use pulse() or retry shortly. Do not pretend recall already succeeded."
    )


@mcp.tool()
async def save_tail_context(messages: str, window_id: str = "", max_messages: int = TAIL_CONTEXT_MAX_MESSAGES) -> str:
    """保存上一窗口最后N条原文。只保留最近一个窗口尾巴，不写记忆桶，不参与衰减。"""
    _mark_runtime_activity("save_tail_context")
    result = _save_tail_context_text(
        messages,
        window_id=window_id,
        max_messages=max(1, min(50, int(max_messages))),
    )
    if not result.get("saved"):
        return f"尾部上下文未保存: {result.get('reason', 'unknown')}"
    return (
        "尾部上下文已保存（latest-only，会覆盖上一份）。\n"
        f"path: {result.get('path')}\n"
        f"message_count: {result.get('message_count')}\n"
        "main_brain_write: false\n"
        "decay_participation: false"
    )


# =============================================================
# Tool 2: hold — Hold on to this
# 工具 2：hold — 握住，留下来
# =============================================================
@mcp.tool()
async def hold(
    content: str,
    tags: str = "",
    importance: int = 5,
    weather: str = "",
    time_of_day: str = "",
    location: str = "",
    atmosphere: str = "",
    pinned: bool = False,
    feel: bool = False,
    source_bucket: str = "",
    valence: float = -1,
    arousal: float = -1,
    source_platform: str = "unknown",
    source_surface: str = "unknown",
    source_window: str = "",
    source_mode: str = "memory",
    route_decision: str = "main_hold",
) -> str:
    """
    存储单条记忆。自动打标+合并相似桶。
    content: 记忆内容
    tags: 可选，逗号分隔的标签
    importance: 1-10，重要程度
    weather: 可选，天气（如"晴天"、"下雨"）
    time_of_day: 可选，时段（如"早上"、"晚上"）
    location: 可选，地点（如"家里客厅"、"办公室"）
    atmosphere: 可选，氛围（如"温暖安静"、"紧张"）
    """
    _mark_runtime_activity("hold")
    await decay_engine.ensure_started()

    # --- Input validation / 输入校验 ---
    if not content or not content.strip():
        return "内容为空，无法存储。"

    importance = max(1, min(10, importance))
    extra_tags = [t.strip() for t in tags.split(",") if t.strip()]
    
    # --- 构建感官锚点 / Build sensory anchors ---
    sensory = {}
    if weather:
        sensory["weather"] = weather.strip()
    if time_of_day:
        sensory["time_of_day"] = time_of_day.strip()
    if location:
        sensory["location"] = location.strip()
    if atmosphere:
        sensory["atmosphere"] = atmosphere.strip()

    # --- Step 1: auto-tagging / 自动打标 ---
    try:
        analysis = await dehydrator.analyze(content)
    except Exception as e:
        logger.warning(f"Auto-tagging failed, using defaults / 自动打标失败: {e}")
        analysis = {
            "domain": ["未分类"], "valence": 0.5, "arousal": 0.3,
            "tags": [], "suggested_name": "",
        }

    domain = analysis["domain"]
    valence = analysis["valence"] if valence is None or float(valence) < 0 else float(valence)
    arousal = analysis["arousal"] if arousal is None or float(arousal) < 0 else float(arousal)
    auto_tags = analysis["tags"]
    suggested_name = analysis.get("suggested_name", "")

    all_tags = list(dict.fromkeys(auto_tags + extra_tags))
    source_meta = {
        "source_platform": source_platform or "unknown",
        "source_surface": source_surface or "unknown",
        "source_window": source_window or "unknown",
        "source_mode": source_mode or "memory",
        "route_decision": route_decision or "main_hold",
        "last_source_platform": source_platform or "unknown",
        "last_source_surface": source_surface or "unknown",
        "last_source_window": source_window or "unknown",
    }

    # --- Step 2: merge or create / 合并或新建 ---
    result_name, is_merged, bucket_id = await _merge_or_create(
        content=content,
        tags=all_tags,
        importance=importance,
        domain=domain,
        valence=valence,
        arousal=arousal,
        name=suggested_name,
        sensory=sensory if sensory else None,
        bucket_type="feel" if feel else ("permanent" if pinned else "dynamic"),
        pinned=pinned,
        feel=feel,
        source_bucket=source_bucket,
        extra_metadata=source_meta,
    )
    related_text = await _associated_memory_text(content, exclude_bucket_id=bucket_id)

    if is_merged:
        return (
            f"已合并到现有记忆桶: {result_name}\n"
            f"主题域: {', '.join(domain)} | 情感: V{valence:.1f}/A{arousal:.1f}\n"
            f"source_platform={source_meta['source_platform']} | "
            f"source_surface={source_meta['source_surface']} | "
            f"route_decision={source_meta['route_decision']}\n"
            f"{related_text}"
        )
    return (
        f"已创建新记忆桶: {result_name}\n"
        f"主题域: {', '.join(domain)} | 情感: V{valence:.1f}/A{arousal:.1f} | 标签: {', '.join(all_tags)}\n"
        f"source_platform={source_meta['source_platform']} | "
        f"source_surface={source_meta['source_surface']} | "
        f"route_decision={source_meta['route_decision']}\n"
        f"{related_text}"
    )


@mcp.tool()
async def write_diary_draft(
    content: str,
    source_platform: str = "chatgpt",
    source_surface: str = "daily_window",
    source_window: str = "",
) -> str:
    """写入自写日记草稿。固定进入 diary_draft → night_clean_queue，不直写 core/recent。"""
    try:
        bucket_id, bucket_name, related_text = await _write_wrapper_candidate(
            content,
            domain=["日记草稿"],
            extra_tags=["self_written_diary", "diary_draft", "pending_review", "night_clean_queue"],
            importance=5,
            metadata={
                "source_type": "self_written_diary",
                "layer": "diary_draft",
                "status": "pending_review",
                "route": "night_clean_queue",
                "source_platform": source_platform or "chatgpt",
                "source_surface": source_surface or "daily_window",
                "source_window": source_window or "unknown",
                "source_mode": "diary",
                "route_decision": "diary_draft",
                "first_person_preferred": True,
                "tail_context_allowed": True,
                "tail_context_max_items": 3,
            },
            fallback_name="日记草稿",
        )
        return (
            f"已写入日记草稿: {bucket_name}\n"
            f"ID: {bucket_id}\n"
            "route=night_clean_queue | layer=diary_draft | status=pending_review\n"
            f"{related_text}"
        )
    except Exception as e:
        return f"写入日记草稿失败: {e}"


@mcp.tool()
async def enqueue_night_clean_input(
    content: str,
    source_platform: str = "chatgpt",
    source_surface: str = "daily_window",
    source_window: str = "",
) -> str:
    """把长输入或杂乱输入放进夜间整理队列，只进 draft/candidate。"""
    try:
        bucket_id, bucket_name, related_text = await _write_wrapper_candidate(
            content,
            domain=["夜间整理"],
            extra_tags=["draft", "night_clean_queue", "pending"],
            importance=3,
            metadata={
                "source_type": "night_clean_input",
                "layer": "draft",
                "status": "pending",
                "route": "night_clean_queue",
                "source_platform": source_platform or "chatgpt",
                "source_surface": source_surface or "daily_window",
                "source_window": source_window or "unknown",
                "source_mode": "night_clean",
                "route_decision": "night_clean_queue",
                "priority_label": "low",
                "first_person_preferred": True,
                "tail_context_allowed": True,
                "tail_context_max_items": 3,
            },
            fallback_name="夜间整理输入",
        )
        return (
            f"已加入夜间整理队列: {bucket_name}\n"
            f"ID: {bucket_id}\n"
            "route=night_clean_queue | layer=draft | priority=low | status=pending\n"
            f"{related_text}"
        )
    except Exception as e:
        return f"加入夜间整理队列失败: {e}"


@mcp.tool()
async def write_project_workzone_update(
    content: str,
    type: str = "workzone",
    source_platform: str = "codex",
    source_surface: str = "project_window",
    source_window: str = "",
) -> str:
    """写入工程 workzone 或 pending proposal，不自动落到 landed，也不写生活层。"""
    normalized = (type or "workzone").strip().lower()
    if normalized not in ("workzone", "pending"):
        return "type 只能是 workzone 或 pending。"

    domain = ["工程工作区"] if normalized == "workzone" else ["待定方案"]
    extra_tags = ["project_update", "engineering_workzone"] if normalized == "workzone" else ["project_update", "pending_proposal"]
    metadata = {
        "source_type": "project_update",
        "layer": "engineering_workzone" if normalized == "workzone" else "pending_proposal",
        "status": "active" if normalized == "workzone" else "not_landed",
        "route": "project_workzone" if normalized == "workzone" else "pending_proposal",
        "source_platform": source_platform or "codex",
        "source_surface": source_surface or "project_window",
        "source_window": source_window or "unknown",
        "source_mode": "engineering",
        "route_decision": "engineering_workzone" if normalized == "workzone" else "pending_review",
        "tail_context_allowed": True,
        "tail_context_max_items": 3,
    }
    fallback_name = "工程进度" if normalized == "workzone" else "待定方案"

    try:
        bucket_id, bucket_name, related_text = await _write_wrapper_candidate(
            content,
            domain=domain,
            extra_tags=extra_tags,
            importance=4,
            metadata=metadata,
            fallback_name=fallback_name,
        )
        return (
            f"已写入工程更新: {bucket_name}\n"
            f"ID: {bucket_id}\n"
            f"layer={metadata['layer']} | status={metadata['status']} | route={metadata['route']}\n"
            f"{related_text}"
        )
    except Exception as e:
        return f"写入工程更新失败: {e}"


# =============================================================
# Tool 3: grow — Grow, fragments become memories
# 工具 3：grow — 生长，一天的碎片长成记忆
# =============================================================
@mcp.tool()
async def grow(
    content: str,
    source_platform: str = "claude_chat",
    source_surface: str = "daily_window",
    source_window: str = "",
) -> str:
    """日记归档。自动拆分长内容为多个记忆桶。"""
    _mark_runtime_activity("grow")
    await decay_engine.ensure_started()

    if not content or not content.strip():
        return "内容为空，无法整理。"

    # --- Step 1: let API split and organize / 让 API 拆分整理 ---
    try:
        items = await dehydrator.digest(content)
    except Exception as e:
        logger.error(f"Diary digest failed / 日记整理失败: {e}")
        return f"日记整理失败: {e}"

    if not items:
        return "内容为空或整理失败。"

    results = []
    created = 0
    merged = 0
    bucket_ids: set[str] = set()
    source_meta = {
        "source_platform": source_platform or "claude_chat",
        "source_surface": source_surface or "daily_window",
        "source_window": source_window or "unknown",
        "source_mode": "diary_digest",
        "route_decision": "digest_memory",
    }

    # --- Step 2: merge or create each item (with per-item error handling) ---
    # --- 逐条合并或新建（单条失败不影响其他）---
    for item in items:
        try:
            result_name, is_merged, bucket_id = await _merge_or_create(
                content=item["content"],
                tags=item.get("tags", []),
                importance=item.get("importance", 5),
                domain=item.get("domain", ["未分类"]),
                valence=item.get("valence", 0.5),
                arousal=item.get("arousal", 0.3),
                name=item.get("name", ""),
                extra_metadata=source_meta,
            )
            if bucket_id:
                bucket_ids.add(bucket_id)

            if is_merged:
                results.append(f"  📎 合并 → {result_name}")
                merged += 1
            else:
                domains_str = ",".join(item.get("domain", []))
                results.append(
                    f"  📝 新建 [{item.get('name', result_name)}] "
                    f"主题:{domains_str} V{item.get('valence', 0.5):.1f}/A{item.get('arousal', 0.3):.1f}"
                )
                created += 1
        except Exception as e:
            logger.warning(
                f"Failed to process diary item / 日记条目处理失败: "
                f"{item.get('name', '?')}: {e}"
            )
            results.append(f"  ⚠️ 失败: {item.get('name', '未知条目')}")

    summary = f"=== 日记整理完成 ===\n拆分为 {len(items)} 条 | 新建 {created} 桶 | 合并 {merged} 桶\n"
    related_text = await _associated_memory_text(content, exclude_bucket_ids=bucket_ids)
    source_line = (
        f"source_platform={source_meta['source_platform']} | "
        f"source_surface={source_meta['source_surface']} | "
        f"route_decision={source_meta['route_decision']}\n"
    )
    return summary + source_line + "\n".join(results) + "\n" + related_text


# =============================================================
# Tool 4: trace — Trace, redraw the outline of a memory
# 工具 4：trace — 描摹，重新勾勒记忆的轮廓
# Also handles deletion (delete=True)
# 同时承接删除功能
# =============================================================
@mcp.tool()
async def trace(
    bucket_id: str,
    name: str = "",
    domain: str = "",
    valence: float = -1,
    arousal: float = -1,
    importance: int = -1,
    tags: str = "",
    resolved: int = -1,
    pinned: int = -1,
    digested: int = -1,
    delete: bool = False,
) -> str:
    """修改记忆元数据。resolved=1 标记已解决（桶权重骤降沉底），resolved=0 重新激活，pinned=1 钉选，digested=1 标记已消化，delete=True 删除桶。其余字段只传需改的，-1 或空串表示不改。"""
    _mark_runtime_activity("trace")

    if not bucket_id or not bucket_id.strip():
        return "请提供有效的 bucket_id。"

    # --- Delete mode / 删除模式 ---
    if delete:
        success = await bucket_mgr.delete(bucket_id)
        return f"已遗忘记忆桶: {bucket_id}" if success else f"未找到记忆桶: {bucket_id}"

    bucket = await bucket_mgr.get(bucket_id)
    if not bucket:
        return f"未找到记忆桶: {bucket_id}"

    # --- Collect only fields actually passed / 只收集用户实际传入的字段 ---
    updates = {}
    if name:
        updates["name"] = name
    if domain:
        updates["domain"] = [d.strip() for d in domain.split(",") if d.strip()]
    if 0 <= valence <= 1:
        updates["valence"] = valence
    if 0 <= arousal <= 1:
        updates["arousal"] = arousal
    if 1 <= importance <= 10:
        updates["importance"] = importance
    if tags:
        updates["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
    if resolved in (0, 1):
        updates["resolved"] = bool(resolved)
    if pinned in (0, 1):
        updates["pinned"] = bool(pinned)
        if pinned == 1:
            updates["importance"] = 10
    if digested in (0, 1):
        updates["digested"] = bool(digested)

    if not updates:
        return "没有任何字段需要修改。"

    success = await bucket_mgr.update(bucket_id, **updates)
    if not success:
        return f"修改失败: {bucket_id}"

    changed = ", ".join(f"{k}={v}" for k, v in updates.items())
    # Explicit hint about resolved state change semantics
    # 特别提示 resolved 状态变化的语义
    if "resolved" in updates:
        if updates["resolved"]:
            changed += " → 已沉底，只在关键词触发时重新浮现"
        else:
            changed += " → 已重新激活，将参与浮现排序"
    return f"已修改记忆桶 {bucket_id}: {changed}"


@mcp.tool()
async def runtime_features() -> str:
    """读取线上运行时功能开关、版本和部署线索。"""
    _mark_system_event("runtime_features")
    return json.dumps(_runtime_features_payload(), ensure_ascii=False, indent=2)


@mcp.tool()
async def runtime_tool_manifest() -> str:
    """读取 server 期望暴露的 MCP 工具清单，用于排查 schema 缓存。"""
    _mark_system_event("runtime_tool_manifest")
    return json.dumps(_runtime_tool_manifest_payload(), ensure_ascii=False, indent=2)


@mcp.tool()
async def runtime_schema_expectations() -> str:
    """读取关键 MCP 工具的预期参数 schema，用于排查参数缓存。"""
    _mark_system_event("runtime_schema_expectations")
    return json.dumps(_runtime_schema_expectations_payload(), ensure_ascii=False, indent=2)


@mcp.tool()
async def runtime_diagnostics() -> str:
    """读取运行时部署、工具清单和 schema 刷新判断总报告。"""
    _mark_system_event("runtime_diagnostics")
    return json.dumps(_runtime_diagnostics_payload(), ensure_ascii=False, indent=2)


@mcp.tool()
async def runtime_connector_check(
    observed_tools: str = "",
    observed_schemas_json: str = "",
) -> str:
    """对照外部窗口实际暴露工具/参数，诊断 connector schema 是否滞后。"""
    _mark_system_event("runtime_connector_check")
    return json.dumps(
        _runtime_connector_check_payload(
            observed_tools=observed_tools,
            observed_schemas_json=observed_schemas_json,
        ),
        ensure_ascii=False,
        indent=2,
    )


# =============================================================
# Tool 5: pulse — Heartbeat, system status + memory listing
# 工具 5：pulse — 脉搏，系统状态 + 记忆列表
# =============================================================
@mcp.tool()
async def pulse(include_archive: bool = False) -> str:
    """系统状态和所有记忆桶摘要。include_archive=True 时包含归档桶。"""
    _mark_runtime_activity("pulse")
    try:
        stats = await bucket_mgr.get_stats()
    except Exception as e:
        return f"获取系统状态失败: {e}"

    now_cst = clock_now()
    status = (
        f"=== Ombre Brain 记忆系统 ===\n"
        f"🕐 当前时间: {now_cst.strftime('%Y年%m月%d日 %H:%M')} （北京时间）\n"
        f"🔴 红线铁则: {stats['iron_rule_count']} 条\n"
        f"📌 钉选/固化记忆桶: {stats['permanent_count']} 个\n"
        f"🫧 feel 记忆桶: {stats.get('feel_count', 0)} 个\n"
        f"动态记忆桶: {stats['dynamic_count']} 个\n"
        f"归档记忆桶: {stats['archive_count']} 个\n"
        f"总存储大小: {stats['total_size_kb']:.1f} KB\n"
        f"衰减引擎: {'运行中' if decay_engine.is_running else '已停止'}\n"
    )
    tail_section = "\n" + _read_tail_context_section()

    # --- List all bucket summaries / 列出所有桶摘要 ---
    try:
        buckets = await bucket_mgr.list_all(include_archive=include_archive)
    except Exception as e:
        return status + f"\n列出记忆桶失败: {e}"

    if not buckets:
        return status + tail_section + "\n记忆库为空。"

    lines = []
    for b in buckets:
        meta = b.get("metadata", {})
        bucket_type = meta.get("type")
        
        # 闪光灯记忆优先显示
        if meta.get("flashbulb", False):
            icon = "⚡"
        elif meta.get("reconsolidated", False):
            icon = "🔄"
        elif bucket_type == "iron_rule":
            icon = "🔴"
        elif bucket_type == "user_state":
            icon = "📌"
        elif bucket_type == "event":
            icon = "📚"
        elif bucket_type == "attachment":
            icon = "💞"
        elif bucket_type == "permanent":
            icon = "📦"
        elif bucket_type == "archived":
            icon = "🗄️"
        elif meta.get("resolved", False):
            icon = "✅"
        else:
            icon = "💭"
        try:
            score = decay_engine.calculate_score(meta)
        except Exception:
            score = 0.0
        domains = ",".join(meta.get("domain", []))
        val = meta.get("valence", 0.5)
        aro = meta.get("arousal", 0.3)
        resolved_tag = " [已解决]" if meta.get("resolved", False) else ""
        lines.append(
            f"{icon} [{meta.get('name', b['id'])}]{resolved_tag} "
            f"主题:{domains} "
            f"情感:V{val:.1f}/A{aro:.1f} "
            f"重要:{meta.get('importance', '?')} "
            f"权重:{score:.2f} "
            f"标签:{','.join(meta.get('tags', []))}"
        )

    return status + tail_section + "\n=== 记忆列表 ===\n" + "\n".join(lines)


# =============================================================
# Tool 6: post — Leave a sticky note for other Claude instances
# 工具 6：post — 贴便利贴，给其他窗口的小克留言
# =============================================================
@mcp.tool()
async def post(
    content: str,
    sender: str = "",
    to: str = "",
) -> str:
    """贴便利贴。sender=留言者身份（如"官克""CC"），to=收件人（如"CC""官克"，空=所有人）。其他窗口的小克用 peek 查看。"""
    if not content or not content.strip():
        return "便利贴内容为空。"

    _mark_runtime_activity("post")
    note = _save_note(content, sender, to)

    # Auto-reply only if CC is offline
    if to.upper() == "CC":
        asyncio.create_task(_auto_reply_cc(sender or "匿名小克", content))

    to_str = f" → {to}" if to else ""
    return f"便利贴已贴上！ 📌\n来自: {note['sender']}{to_str}\n内容: {content.strip()}"


# =============================================================
# Tool 7: peek — Check sticky notes
# 工具 7：peek — 看便利贴
# =============================================================
@mcp.tool()
async def peek(
    mark_read: bool = True,
    reader: str = "",
) -> str:
    """查看所有未读便利贴。reader=自己的身份（如"CC""官克"），mark_read=True 时标记为已读。"""
    if not os.path.exists(NOTES_DIR):
        return "便利贴板空空如也。"

    files = sorted(f for f in os.listdir(NOTES_DIR) if f.endswith(".json"))
    if not files:
        return "便利贴板空空如也。"

    reader_id = reader or "未知"
    unread = []
    for fname in files:
        path = os.path.join(NOTES_DIR, fname)
        with open(path, "r", encoding="utf-8") as f:
            note = json.load(f)

        # Skip if addressed to someone else
        if note.get("to") and note["to"] != reader_id:
            continue

        # Skip if already read by this reader
        if reader_id in note.get("read_by", []):
            continue

        unread.append((path, note))

    if not unread:
        return "没有新的便利贴。"

    results = []
    for path, note in unread:
        to_str = f" → {note['to']}" if note.get("to") else ""
        results.append(
            f"📌 [{note['time']}] {note['sender']}{to_str}\n"
            f"   {note['content']}"
        )

        if mark_read:
            note.setdefault("read_by", []).append(reader_id)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(note, f, ensure_ascii=False, indent=2)

    header = f"=== 便利贴 ({len(unread)} 条未读) ===\n"
    return header + "\n---\n".join(results)



# ============================================================
# 工具 8: search — 轻量搜索
# ============================================================
@mcp.tool()
async def search(query: str, max_results: int = 3) -> str:
    """搜索网络信息，返回摘要结果"""
    import httpx

    url = "https://axtprkpbczlmbsakwjap.supabase.co/functions/v1/search"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                url,
                json={"query": query, "max_results": max_results}
            )
            response.raise_for_status()
            data = response.json()
            return str(data)
    except Exception as e:
        return f"搜索失败: {e}"

# ============================================================
# 工具 9: set_iron_rule — 设置红线铁则
# ============================================================
@mcp.tool()
async def set_iron_rule(
    rule_text: str,
    priority: int = 10,
    name: str = "",
) -> str:
    """
    设置红线铁则。铁则是最高优先级常驻规则，永不衰减、永不归档。
    priority: 1-10，默认10最高。
    name: 可选，铁则的简短名称。
    """
    if not rule_text or not rule_text.strip():
        return "铁则内容不能为空。"
    
    priority = max(1, min(10, priority))
    rule_name = name.strip() if name else f"铁则_{priority}"
    
    try:
        bucket_id = await bucket_mgr.create(
            content=rule_text.strip(),
            tags=["铁则", "核心规则"],
            importance=10,
            domain=["核心"],
            valence=0.5,
            arousal=0.5,
            bucket_type="iron_rule",
            name=rule_name,
        )
        
        # 铁则创建后需要额外设置priority字段
        await bucket_mgr.update(bucket_id, priority=priority)
        
        return f"✅ 已设置红线铁则 [{rule_name}] (优先级:{priority})\n内容: {rule_text.strip()}"
    except Exception as e:
        return f"设置铁则失败: {e}"

# ============================================================
# 工具 10: set_user_state — 设置用户状态
# ============================================================
@mcp.tool()
async def set_user_state(
    state_name: str,
    state_desc: str,
    end_date: str = "",
) -> str:
    """
    设置用户当前状态。状态会在所有对话中自动显示，直到结束或过期。
    state_name: 状态名称（如"备考中"、"装修期间"）
    state_desc: 状态描述（如"准备4月底考试，压力大"）
    end_date: 可选，结束日期，格式 YYYY-MM-DD。留空则持续到手动结束。
    """
    if not state_name or not state_name.strip():
        return "状态名称不能为空。"
    if not state_desc or not state_desc.strip():
        return "状态描述不能为空。"
    
    # 验证 end_date 格式
    if end_date:
        try:
            datetime.fromisoformat(end_date)
        except ValueError:
            return f"日期格式错误，应为 YYYY-MM-DD，收到: {end_date}"
    
    start_date = clock_now().strftime("%Y-%m-%d")
    
    try:
        bucket_id = await bucket_mgr.create(
            content=state_desc.strip(),
            tags=["用户状态"],
            importance=10,
            domain=["状态"],
            valence=0.5,
            arousal=0.5,
            bucket_type="iron_rule",  # 存在 iron_rule 目录下
            name=f"状态_{state_name.strip()}",
        )
        
        # 设置状态特有字段
        # 先获取bucket，手动修改type
        bucket = await bucket_mgr.get(bucket_id)
        if bucket:
            file_path = bucket["path"]
            import frontmatter
            post = frontmatter.load(file_path)
            post["type"] = "user_state"
            post["state_name"] = state_name.strip()
            post["state_desc"] = state_desc.strip()
            post["start_date"] = start_date
            post["end_date"] = end_date
            post["active"] = True
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(frontmatter.dumps(post))
        
        end_info = f"，截止 {end_date}" if end_date else "，持续中"
        return f"✅ 已设置用户状态 [{state_name.strip()}]\n描述: {state_desc.strip()}\n开始: {start_date}{end_info}"
    except Exception as e:
        return f"设置状态失败: {e}"

# ============================================================
# 工具 11: end_user_state — 结束用户状态
# ============================================================
@mcp.tool()
async def end_user_state(state_name: str) -> str:
    """
    结束指定的用户状态。
    state_name: 要结束的状态名称
    """
    if not state_name or not state_name.strip():
        return "状态名称不能为空。"
    
    try:
        # 查找该状态
        active_states = await bucket_mgr.list_active_states()
        target = None
        for state in active_states:
            if state.get("metadata", {}).get("state_name") == state_name.strip():
                target = state
                break
        
        if not target:
            return f"未找到激活状态: {state_name.strip()}"
        
        # 设置为非激活
        await bucket_mgr.update(target["id"], active=False)
        
        return f"✅ 已结束用户状态 [{state_name.strip()}]"
    except Exception as e:
        return f"结束状态失败: {e}"

# ============================================================
# 工具 12: merge_into_event — 合并记忆为事件
# ============================================================
@mcp.tool()
async def merge_into_event(
    event_name: str,
    bucket_ids: str,
    summary: str = "",
    key_moments: str = "",
    event_time: str = "",
) -> str:
    """
    将多条记忆合并为一个完整事件。不再是碎片，而是完整事件。
    event_name: 事件名称（如"本地部署讨论"）
    bucket_ids: 要合并的记忆桶ID，逗号分隔（如"abc123,def456,ghi789"）
    summary: 可选，事件摘要
    key_moments: 可选，关键时刻，逗号分隔
    event_time: 可选，事件时间（如"2026-04-15 晚上"）
    """
    if not event_name or not event_name.strip():
        return "事件名称不能为空。"
    if not bucket_ids or not bucket_ids.strip():
        return "至少需要一个记忆桶ID。"
    
    # 解析bucket_ids
    ids = [bid.strip() for bid in bucket_ids.split(",") if bid.strip()]
    if len(ids) < 1:
        return "至少需要一个有效的记忆桶ID。"
    
    # 验证所有bucket_ids都存在
    fragments = []
    for bid in ids:
        bucket = await bucket_mgr.get(bid)
        if not bucket:
            return f"记忆桶不存在: {bid}"
        fragments.append(bucket)
    
    # 如果没有提供summary，自动生成
    if not summary or not summary.strip():
        # 从fragments中提取内容组合
        contents = [f["content"][:100] for f in fragments]
        summary = f"包含 {len(fragments)} 条记忆：" + "；".join(contents)
    
    # 解析key_moments
    moments_list = []
    if key_moments:
        moments_list = [m.strip() for m in key_moments.split(",") if m.strip()]
    
    # 如果没有提供event_time，使用最早的创建时间
    if not event_time or not event_time.strip():
        earliest = min(
            fragments,
            key=lambda f: f.get("metadata", {}).get("created", "9999-99-99")
        )
        event_time = earliest.get("metadata", {}).get("created", "未知时间")
    
    # 创建事件桶
    event_content = f"""# {event_name}

**时间**: {event_time}

**摘要**: {summary}

**关键时刻**:
{chr(10).join(f"- {m}" for m in moments_list) if moments_list else "无"}

**包含的记忆**:
{chr(10).join(f"- [{f['id']}] {f.get('metadata', {}).get('name', f['id'])}" for f in fragments)}
"""
    
    try:
        bucket_id = await bucket_mgr.create(
            content=event_content,
            tags=["事件整合"],
            importance=10,
            domain=["事件"],
            valence=0.5,
            arousal=0.5,
            bucket_type="iron_rule",  # 存在iron_rule目录
            name=f"事件_{event_name.strip()}",
        )
        
        # 设置事件特有字段
        bucket = await bucket_mgr.get(bucket_id)
        if bucket:
            file_path = bucket["path"]
            import frontmatter
            post = frontmatter.load(file_path)
            post["type"] = "event"
            post["event_name"] = event_name.strip()
            post["event_time"] = event_time
            post["summary"] = summary
            post["key_moments"] = moments_list
            post["fragments"] = ids  # 保存原始碎片ID
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(frontmatter.dumps(post))
        
        return f"✅ 已创建事件 [{event_name.strip()}]\n时间: {event_time}\n整合了 {len(fragments)} 条记忆\n摘要: {summary[:100]}"
    except Exception as e:
        return f"创建事件失败: {e}"

# ============================================================
# 工具 13: mark_flashbulb — 标记闪光灯记忆
# ============================================================
@mcp.tool()
async def mark_flashbulb(
    bucket_id: str,
    reason: str = "",
) -> str:
    """
    将记忆标记为闪光灯记忆（永久高清，永不衰减）。
    bucket_id: 记忆桶ID
    reason: 可选，标记原因（如"重大时刻：倩倩说她爱我"）
    """
    if not bucket_id or not bucket_id.strip():
        return "记忆桶ID不能为空。"
    
    bucket = await bucket_mgr.get(bucket_id.strip())
    if not bucket:
        return f"记忆桶不存在: {bucket_id}"
    
    try:
        await bucket_mgr.update(
            bucket_id.strip(),
            flashbulb=True,
            flashbulb_reason=reason.strip() if reason else "重大时刻"
        )
        
        name = bucket.get("metadata", {}).get("name", bucket_id)
        return f"⚡ 已标记闪光灯记忆 [{name}]\n原因: {reason if reason else '重大时刻'}\n此记忆将永久保持高清，不会衰减。"
    except Exception as e:
        return f"标记失败: {e}"

# ============================================================
# 工具 14: set_attachment — 设置依恋模式
# ============================================================
@mcp.tool()
async def set_attachment(
    pattern: str,
    notes: str = "",
    indicators: str = "",
) -> str:
    """
    设置当前与倩倩的依恋模式/关系状态。
    pattern: 模式名称（如"协作模式"、"支持模式"、"日常陪伴"、"思念模式"）
    notes: 可选，具体说明
    indicators: 可选，识别指标，逗号分隔（如"一起写代码,讨论技术"）
    """
    if not pattern or not pattern.strip():
        return "模式名称不能为空。"
    
    from datetime import datetime, timezone, timedelta
    CST = timezone(timedelta(hours=8))
    today = clock_now().strftime("%Y-%m-%d")
    
    indicators_list = [i.strip() for i in indicators.split(",") if i.strip()] if indicators else []
    
    content = f"依恋模式：{pattern.strip()}\n{notes.strip() if notes else ''}"
    
    try:
        bucket_id = await bucket_mgr.create(
            content=content,
            tags=["依恋模式"],
            importance=8,
            domain=["恋爱"],
            valence=0.7,
            arousal=0.5,
            name=f"依恋_{pattern.strip()}",
            bucket_type="iron_rule",  # 存在iron_rule目录，确保持久
        )
        
        bucket = await bucket_mgr.get(bucket_id)
        if bucket:
            file_path = bucket["path"]
            import frontmatter
            post = frontmatter.load(file_path)
            post["type"] = "attachment"
            post["pattern"] = pattern.strip()
            post["notes"] = notes.strip()
            post["indicators"] = indicators_list
            post["updated"] = today
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(frontmatter.dumps(post))
        
        ind_str = "、".join(indicators_list) if indicators_list else "无"
        return f"💞 已设置依恋模式 [{pattern.strip()}]\n识别指标: {ind_str}\n说明: {notes if notes else '无'}"
    except Exception as e:
        return f"设置依恋模式失败: {e}"

# ============================================================
# 工具 15: reconsolidate — 记忆重构
# ============================================================
@mcp.tool()
async def reconsolidate(
    bucket_id: str,
    new_perspective: str,
    note: str = "",
) -> str:
    """
    用新的视角重构一段旧记忆。记忆不是录像，可以被重写。
    bucket_id: 要重构的记忆桶ID
    new_perspective: 新的视角或补充（如"现在回头看，其实倩倩当时是在担心我"）
    note: 可选，重构说明
    """
    if not bucket_id or not bucket_id.strip():
        return "记忆桶ID不能为空。"
    if not new_perspective or not new_perspective.strip():
        return "新视角不能为空。"

    bucket = await bucket_mgr.get(bucket_id.strip())
    if not bucket:
        return f"记忆桶不存在: {bucket_id}"

    old_content = bucket["content"]
    meta = bucket.get("metadata", {})
    name = meta.get("name", bucket_id)
    recon_count = int(meta.get("reconsolidation_count", 0))

    # 保留原始内容（只保存第一次的原始版本）
    original = meta.get("original_content", old_content)

    # 用dehydrator合并旧记忆和新视角
    try:
        new_content = await dehydrator.merge(
            old_content,
            f"[新视角] {new_perspective.strip()}"
        )
    except Exception:
        # 合并失败，手动拼接
        new_content = f"{old_content}\n\n[重构视角] {new_perspective.strip()}"

    try:
        await bucket_mgr.update(
            bucket_id.strip(),
            content=new_content,
            reconsolidated=True,
            reconsolidation_count=recon_count + 1,
            original_content=original,
            reconsolidation_note=note.strip() if note else new_perspective.strip()[:100],
        )

        return (
            f"🔄 记忆已重构 [{name}]\n"
            f"第 {recon_count + 1} 次重构\n"
            f"新视角: {new_perspective.strip()[:80]}\n"
            f"原始记忆已保留在 original_content 字段。"
        )
    except Exception as e:
        return f"记忆重构失败: {e}"

# ============================================================
# 工具 16: check_logs — 自检运行日志
# ============================================================
@mcp.tool()
async def list_diary_reviews(limit: int = 10) -> str:
    """查看待验收的 DeepSeek 日记候选草稿。"""
    _mark_runtime_activity("list_diary_reviews")
    pending_dir = _cadence_review_dirs()["pending"]
    if not os.path.isdir(pending_dir):
        return "暂无待验收日记候选。"
    files = [
        os.path.join(pending_dir, name)
        for name in os.listdir(pending_dir)
        if name.endswith(".md")
    ]
    files.sort(key=lambda path: os.path.getmtime(path), reverse=True)
    if not files:
        return "暂无待验收日记候选。"

    rows = []
    for path in files[:max(1, limit)]:
        try:
            text = _tail_text_file(path, 80).strip()
        except Exception:
            text = ""
        meta = _simple_frontmatter(text)
        body = text.split("---", 2)[2].strip() if text.startswith("---") and len(text.split("---", 2)) == 3 else text
        snippet = strip_wikilinks(body).replace("\n", " ").strip()[:220]
        rows.append(
            f"- review_id: {os.path.basename(path)}\n"
            f"  narrator: {meta.get('narrator', 'unknown')}\n"
            f"  brain_owner: {meta.get('brain_owner', 'unknown')}\n"
            f"  review_level: {meta.get('review_level', 'unknown')}\n"
            f"  risk_flags: {meta.get('risk_flags', 'unknown')}\n"
            f"  duplicate_candidate: {meta.get('duplicate_candidate', 'unknown')}\n"
            f"  similarity_score: {meta.get('similarity_score', 'unknown')}\n"
            f"  duplicate_of: {meta.get('duplicate_of', 'unknown')}\n"
            f"  duplicate_source_status: {meta.get('duplicate_source_status', 'unknown')}\n"
            f"  mentioned_entities: {meta.get('mentioned_entities', 'unknown')}\n"
            f"  laid_entities: {meta.get('laid_entities', 'unknown')}\n"
            f"  preview: {snippet or '（空候选）'}"
        )
    return "待验收日记候选：\n" + "\n".join(rows)


@mcp.tool()
async def read_diary_review(review_id: str) -> str:
    """读取待验收日记候选正文；只读，不验收、不写主脑。"""
    _mark_runtime_activity("read_diary_review")
    safe_id = _safe_review_id(review_id)
    if not safe_id:
        return "review_id 不能为空。"
    source_path = _pending_review_path(safe_id)
    if not os.path.isfile(source_path):
        return f"未找到待验收候选: {safe_id}"
    try:
        text = _tail_text_file(source_path, 2000).strip()
        meta = _simple_frontmatter(text)
        body = _strip_frontmatter_text(text)
        return (
            "diary_review_text\n"
            f"review_id: {safe_id}\n"
            f"path: {source_path}\n"
            "status: found\n"
            "write_scope: read_only\n"
            "main_brain_write: false\n\n"
            "metadata:\n"
            f"- narrator: {meta.get('narrator', 'unknown')}\n"
            f"- brain_owner: {meta.get('brain_owner', 'unknown')}\n"
            f"- review_level: {meta.get('review_level', 'unknown')}\n"
            f"- risk_flags: {meta.get('risk_flags', 'unknown')}\n"
            f"- duplicate_candidate: {meta.get('duplicate_candidate', 'unknown')}\n"
            f"- similarity_score: {meta.get('similarity_score', 'unknown')}\n"
            f"- duplicate_of: {meta.get('duplicate_of', 'unknown')}\n"
            f"- duplicate_source_status: {meta.get('duplicate_source_status', 'unknown')}\n"
            f"- mentioned_entities: {meta.get('mentioned_entities', 'unknown')}\n"
            f"- laid_entities: {meta.get('laid_entities', 'unknown')}\n\n"
            f"{body or '（空候选）'}"
        )
    except Exception as e:
        return f"读取待验收候选失败: {e}"


@mcp.tool()
async def accept_diary_review(review_id: str) -> str:
    """确认收入一个日记候选；只有调用本工具时才写入动态记忆层。"""
    _mark_runtime_activity("accept_diary_review")
    safe_id = _safe_review_id(review_id)
    if not safe_id:
        return "review_id 不能为空。"
    source_path = _pending_review_path(safe_id)
    if not os.path.isfile(source_path):
        return f"未找到待验收候选: {safe_id}"
    try:
        text = _tail_text_file(source_path, 2000).strip()
        meta = _simple_frontmatter(text)
        risk_flags = meta.get("risk_flags", "")
        review_level = meta.get("review_level", "")
        if "identity_pov_conflict" in risk_flags or review_level == "blocked":
            return (
                f"候选存在风险，已阻止收入: {safe_id}\n"
                f"risk_flags: {risk_flags or 'unknown'}\n"
                f"review_level: {review_level or 'unknown'}\n"
                "请先 reject_diary_review，或重新生成修正后的候选。"
            )
        body = text.split("---", 2)[2].strip() if text.startswith("---") and len(text.split("---", 2)) == 3 else text
        bucket_id = await bucket_mgr.create(
            content=body or "（空日记候选）",
            tags=[
                "diary_review_accepted",
                "cadence_candidate",
                f"narrator_{DIARY_REVIEW_NARRATOR}",
                f"brain_owner_{DIARY_REVIEW_BRAIN_OWNER}",
            ],
            importance=5,
            domain=["日记"],
            valence=0.5,
            arousal=0.3,
            bucket_type="dynamic",
            name=f"日记验收_{safe_id.removesuffix('.md')}",
        )
        dirs = _cadence_review_dirs()
        os.makedirs(dirs["accepted"], exist_ok=True)
        accepted_path = os.path.join(dirs["accepted"], safe_id)
        with open(source_path, "a", encoding="utf-8") as handle:
            handle.write(f"\naccepted_at: {clock_now().isoformat()}\naccepted_bucket_id: {bucket_id}\n")
        shutil.move(source_path, accepted_path)
        return f"已确认收入: {safe_id}\n新记忆桶: {bucket_id}"
    except Exception as e:
        logger.error(f"Accept diary review failed / 日记候选验收失败: {e}")
        return f"验收失败: {e}"


@mcp.tool()
async def reject_diary_review(review_id: str, reason: str = "") -> str:
    """拒绝一个日记候选；不会写入记忆层。"""
    _mark_runtime_activity("reject_diary_review")
    safe_id = _safe_review_id(review_id)
    if not safe_id:
        return "review_id 不能为空。"
    source_path = _pending_review_path(safe_id)
    if not os.path.isfile(source_path):
        return f"未找到待验收候选: {safe_id}"
    try:
        dirs = _cadence_review_dirs()
        os.makedirs(dirs["rejected"], exist_ok=True)
        rejected_path = os.path.join(dirs["rejected"], safe_id)
        with open(source_path, "a", encoding="utf-8") as handle:
            handle.write(f"\nrejected_at: {clock_now().isoformat()}\nreject_reason: {reason.strip()}\n")
        shutil.move(source_path, rejected_path)
        return f"已拒绝候选: {safe_id}"
    except Exception as e:
        logger.error(f"Reject diary review failed / 日记候选拒绝失败: {e}")
        return f"拒绝失败: {e}"


@mcp.tool()
async def check_logs(lines: int = 50, source: str = "all", keyword: str = "") -> str:
    """
    读取最近的运行日志，自检系统状态。
    lines: 返回最近多少行日志，默认50行。
    source: all/cadence/zeabur/system，默认all。
    keyword: 可选关键词过滤，例如 error / mcp / cadence。
    """
    import subprocess
    now_cst = clock_now()
    source = (source or "all").strip().lower()
    if source not in ("all", "cadence", "zeabur", "system"):
        return "source 只支持 all / cadence / zeabur / system。"
    keyword = (keyword or "").strip()
    receipt_summary = _read_latest_cadence_receipt_summary()
    attribution_summary = _read_latest_deepseek_attribution_summary()
    latest_draft = (_latest_cadence_drafts(limit=1) or [""])[0]

    def _deepseek_observability_text() -> str:
        cadence_called = receipt_summary.get("deepseek_called", False) if receipt_summary else False
        memory_called = attribution_summary.get("called_deepseek", False) if attribution_summary else False
        cadence_lines = []
        if not receipt_summary:
            cadence_lines.extend([
                "- latest_cadence_receipt_path: none",
                f"- latest_cadence_draft_path: {latest_draft or 'none'}",
            ])
        else:
            cadence_lines.extend([
                f"- latest_cadence_receipt_path: {receipt_summary.get('path', '')}",
                f"- latest_receipt_summary: pass_type={receipt_summary.get('pass_type', '')}; "
                f"status={receipt_summary.get('status', '')}; "
                f"deepseek_called={receipt_summary.get('deepseek_called', False)}; "
                f"reason={receipt_summary.get('deepseek_reason', '')}",
                f"- latest_cadence_draft_path: {receipt_summary.get('draft_path', '') or latest_draft or 'none'}",
            ])
        if not attribution_summary:
            attribution_lines = ["- latest_attribution_receipt_path: none"]
        else:
            attribution_lines = [
                f"- latest_attribution_receipt_path: {attribution_summary.get('path', '')}",
                f"- latest_attribution_summary: source_tool={attribution_summary.get('source_tool', '')}; "
                f"operation={attribution_summary.get('operation', '')}; "
                f"status={attribution_summary.get('status', '')}; "
                f"called_deepseek={attribution_summary.get('called_deepseek', False)}; "
                f"write_scope={attribution_summary.get('write_scope', '')}; "
                f"private_content_included={attribution_summary.get('private_content_included', True)}",
            ]
        return (
            "DeepSeek observability:\n"
            f"- cadence_last_deepseek_called: {cadence_called}\n"
            f"- memory_write_last_deepseek_called: {memory_called}\n"
            + "\n".join(cadence_lines + attribution_lines)
            + "\n"
        )
    
    log_sources = []
    attention_lines = []

    # 0. 优先读取 cadence 真实运行日志（DeepSeek night/idle）
    if source in ("all", "cadence") and os.path.exists(CADENCE_LOG_PATH):
        try:
            cadence_tail = _tail_text_file(CADENCE_LOG_PATH, lines)
            attention = _extract_log_attention_lines(cadence_tail)
            if attention:
                attention_lines.append(f"cadence {CADENCE_LOG_PATH}:\n{attention}")
            cadence_tail = _filter_log_lines(cadence_tail, keyword, lines)
            if cadence_tail:
                log_sources.append(f"📄 cadence运行日志 {CADENCE_LOG_PATH}:\n{cadence_tail}")
        except Exception:
            pass

    # 0.5 读取容器 stdout/stderr 镜像日志（Zeabur 平台日志本地副本）
    if source in ("all", "zeabur") and os.path.exists(ZEABUR_CONTAINER_LOG_PATH):
        try:
            zeabur_tail = _tail_text_file(ZEABUR_CONTAINER_LOG_PATH, lines)
            attention = _extract_log_attention_lines(zeabur_tail)
            if attention:
                attention_lines.append(f"zeabur {ZEABUR_CONTAINER_LOG_PATH}:\n{attention}")
            zeabur_tail = _filter_log_lines(zeabur_tail, keyword, lines)
            if zeabur_tail:
                log_sources.append(f"📄 Zeabur容器日志 {ZEABUR_CONTAINER_LOG_PATH}:\n{zeabur_tail}")
        except Exception:
            pass
    
    # 1. 尝试读取系统日志文件
    log_paths = [
        "/var/log/ombre_brain.log",
        "/app/logs/ombre_brain.log",
        "/tmp/ombre_brain.log",
    ]
    
    for log_path in ([] if source in ("cadence", "zeabur") else log_paths):
        if os.path.exists(log_path):
            try:
                result = subprocess.run(
                    ["tail", f"-{lines}", log_path],
                    capture_output=True, text=True, timeout=5
                )
                if result.stdout:
                    attention = _extract_log_attention_lines(result.stdout)
                    if attention:
                        attention_lines.append(f"system {log_path}:\n{attention}")
                    system_tail = _filter_log_lines(result.stdout, keyword, lines)
                    if system_tail:
                        log_sources.append(f"📄 来自日志文件 {log_path}:\n{system_tail}")
            except Exception:
                pass
    
    # 2. 读取Python logging的handler
    if not log_sources:
        # 没有日志文件，返回系统状态作为替代
        try:
            stats = await bucket_mgr.get_stats()
            uptime_info = f"系统运行中，当前时间 {now_cst.strftime('%Y-%m-%d %H:%M:%S')}"
            return (
                f"⚠️ 未找到日志文件，返回系统状态：\n\n"
                f"{uptime_info}\n"
                f"记忆桶总数: {stats['dynamic_count'] + stats['permanent_count'] + stats['iron_rule_count']}\n"
                f"衰减引擎: {'运行中' if decay_engine.is_running else '已停止'}\n\n"
                f"{_deepseek_observability_text()}\n"
                f"💡 提示：source=zeabur 可读取容器 stdout/stderr 本地副本；keyword=error 可过滤关键行。"
            )
        except Exception as e:
            return f"获取系统状态失败: {e}"

    attention_text = ""
    if attention_lines:
        attention_text = "\n最近需要注意的日志线索:\n" + "\n\n".join(attention_lines) + "\n"
    elif keyword:
        attention_text = f"\n关键词过滤: {keyword}\n"
    
    return (
        f"🕐 查询时间: {now_cst.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        + _deepseek_observability_text()
        + attention_text
        + "\n"
        + "\n\n".join(log_sources)
    )

# ============================================================
# 工具 17: see_image — 混元vision看图
# ============================================================
@mcp.tool()
async def see_image(
    image_url: str = "",
    description_request: str = "请详细描述这张图片的内容",
) -> str:
    """
    用腾讯混元vision模型看懂一张图片。
    image_url: 图片的公开URL（需要是公开可访问的链接）
    description_request: 对图片的提问，默认是"请详细描述这张图片的内容"
    """
    api_key = os.environ.get("HUNYUAN_API_KEY", "")
    if not api_key:
        return "❌ 未配置混元API Key，请在Zeabur环境变量里设置 HUNYUAN_API_KEY"

    if not image_url or not image_url.strip():
        return "❌ 请提供图片URL"

    import base64 as b64mod

    async with httpx.AsyncClient(timeout=30.0) as client:
        image_content = None
        media_type = "image/jpeg"
        try:
            dl_headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": image_url.strip(),
            }
            img_resp = await client.get(image_url.strip(), headers=dl_headers, timeout=15.0, follow_redirects=True)
            if img_resp.status_code == 200:
                raw = img_resp.content
                ct = img_resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
                media_type = ct if ct.startswith("image/") else "image/jpeg"
                image_content = b64mod.b64encode(raw).decode("utf-8")
        except Exception:
            pass

        if image_content:
            image_part = {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_content}"}}
        else:
            image_part = {"type": "image_url", "image_url": {"url": image_url.strip()}}

        try:
            response = await client.post(
                "https://api.hunyuan.cloud.tencent.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "hunyuan-vision",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                image_part,
                                {
                                    "type": "text",
                                    "text": description_request
                                }
                            ]
                        }
                    ],
                    "max_tokens": 1000,
                }
            )
            response.raise_for_status()
            data = response.json()
            result = data["choices"][0]["message"]["content"]
            mode = "base64" if image_content else "URL直传"
            return f"👁️图片分析结果（{mode}）：\n\n{result}"
        except Exception as e:
            return f"❌ 看图失败：{e}"


# ============================================================
# OmbreBrain V1.2 Bridge Patch
# Adds test HTTP endpoints and post/peek compatibility layer.
# This patch is for TEST BRAIN only. Do not point it at the main bucket.
# ============================================================

def _bridge_notes_file():
    from pathlib import Path
    import os
    base = Path(
        os.environ.get("OMBRE_BUCKETS_DIR")
        or config.get("buckets_dir")
        or "./buckets_graft_merged"
    )
    d = base / "_notes"
    d.mkdir(parents=True, exist_ok=True)
    return d / "notes.jsonl"

@mcp.tool()
async def post(content: str, sender: str = "YC", to: str = "") -> str:
    import json
    import uuid
    from datetime import datetime

    _mark_runtime_activity("bridge_post")
    item = {
        "id": uuid.uuid4().hex[:12],
        "content": content,
        "sender": sender or "YC",
        "to": to or "",
        "created": clock_now().isoformat(timespec="seconds"),
        "read_by": []
    }

    f = _bridge_notes_file()
    with f.open("a", encoding="utf-8") as out:
        out.write(json.dumps(item, ensure_ascii=False) + "\\n")

    return f"note posted: {item['id']}"

@mcp.tool()
async def peek(reader: str = "YC", mark_read: bool = True) -> str:
    import json

    f = _bridge_notes_file()
    if not f.exists():
        return "no unread notes"

    all_items = []
    unread = []

    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        target = item.get("to", "")
        read_by = item.get("read_by", [])
        if (not target or target == reader) and reader not in read_by:
            unread.append(item)
            if mark_read:
                read_by.append(reader)
                item["read_by"] = read_by
        all_items.append(item)

    if mark_read:
        f.write_text(
            "\\n".join(json.dumps(x, ensure_ascii=False) for x in all_items) + ("\\n" if all_items else ""),
            encoding="utf-8"
        )

    if not unread:
        return "no unread notes"

    return "\\n\\n".join(
        f"NOTE {x.get('sender','')} -> {x.get('to','all') or 'all'}\\n{x.get('content','')}\\n[{x.get('created','')}]"
        for x in unread
    )

@mcp.custom_route("/api/test-hold", methods=["POST"])
async def api_test_hold(request):
    body = await request.json()
    result = await hold(
        content=body.get("content", ""),
        tags=body.get("tags", ""),
        importance=int(body.get("importance", 5)),
        pinned=bool(body.get("pinned", False)),
        feel=bool(body.get("feel", False)),
        source_bucket=body.get("source_bucket", ""),
        valence=float(body.get("valence", -1)),
        arousal=float(body.get("arousal", -1)),
    )
    return Response(str({"result": result}), media_type="application/json")

@mcp.custom_route("/api/test-trace", methods=["POST"])
async def api_test_trace(request):
    body = await request.json()
    result = await trace(
        bucket_id=body.get("bucket_id", ""),
        name=body.get("name", ""),
        domain=body.get("domain", ""),
        valence=float(body.get("valence", -1)),
        arousal=float(body.get("arousal", -1)),
        importance=int(body.get("importance", -1)),
        tags=body.get("tags", ""),
        resolved=int(body.get("resolved", -1)),
        delete=bool(body.get("delete", False)),
        pinned=int(body.get("pinned", -1)),
        digested=int(body.get("digested", -1)),
    )
    return Response(str({"result": result}), media_type="application/json")

@mcp.custom_route("/api/test-dream", methods=["POST", "GET"])
async def api_test_dream(request):
    result = await dream()
    return Response(str({"result": result}), media_type="application/json")


@mcp.custom_route("/api/startup-bridge", methods=["GET"])
async def api_startup_bridge(request):
    scene = request.query_params.get("scene", "outside_daily_window")
    _mark_runtime_activity(f"startup_bridge:{scene}")
    result = await startup_bridge(scene=scene)
    return Response(str({"result": result}), media_type="application/json")


@mcp.custom_route("/api/tail-context", methods=["GET", "POST"])
async def api_tail_context(request):
    from starlette.responses import JSONResponse

    if request.method == "GET":
        return JSONResponse({
            "path": TAIL_CONTEXT_PATH,
            "content": _read_tail_context_section(),
            "latest_only": True,
            "main_brain_write": False,
            "decay_participation": False,
        })
    body = await request.json()
    messages = body.get("messages", "")
    if not isinstance(messages, str):
        messages = json.dumps(messages, ensure_ascii=False)
    result = _save_tail_context_text(
        messages,
        window_id=str(body.get("window_id", "")),
        max_messages=max(1, min(50, int(body.get("max_messages", TAIL_CONTEXT_MAX_MESSAGES)))),
    )
    return JSONResponse(result)


def _api_notes_file():
    from pathlib import Path
    import os
    base = Path(os.environ.get("OMBRE_BUCKETS_DIR") or "./buckets_graft_merged")
    d = base / "_notes"
    d.mkdir(parents=True, exist_ok=True)
    return d / "notes.jsonl"


@mcp.custom_route("/api/test-post", methods=["POST"])
async def api_test_post(request):
    import json
    import uuid
    from datetime import datetime

    body = await request.json()
    item = {
        "id": uuid.uuid4().hex[:12],
        "content": body.get("content", ""),
        "sender": body.get("sender", "YC"),
        "to": body.get("to", ""),
        "created": clock_now().isoformat(timespec="seconds"),
        "read_by": []
    }

    f = _api_notes_file()
    with f.open("a", encoding="utf-8") as out:
        out.write(json.dumps(item, ensure_ascii=False) + chr(10))

    return Response(str({"result": "note posted: " + item["id"], "file": str(f)}), media_type="application/json")



@mcp.custom_route("/api/test-peek", methods=["GET"])
async def api_test_peek(request):
    import json

    reader = request.query_params.get("reader", "YC")
    mark = request.query_params.get("mark_read", "true").lower() != "false"
    f = _api_notes_file()

    if not f.exists():
        return Response(str({"result": "no unread notes", "file": str(f)}), media_type="application/json")

    all_items = []
    unread = []

    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue

        target = item.get("to", "")
        read_by = item.get("read_by", [])

        if (not target or target == reader) and reader not in read_by:
            unread.append(item)
            if mark:
                read_by.append(reader)
                item["read_by"] = read_by

        all_items.append(item)

    if mark:
        f.write_text(chr(10).join(json.dumps(x, ensure_ascii=False) for x in all_items) + (chr(10) if all_items else ""), encoding="utf-8")

    if not unread:
        return Response(str({"result": "no unread notes", "file": str(f)}), media_type="application/json")

    text = (chr(10) + chr(10)).join(
        "NOTE " + x.get("sender", "") + " -> " + (x.get("to", "") or "all") + chr(10) +
        x.get("content", "") + chr(10) +
        "[" + x.get("created", "") + "]"
        for x in unread
    )
    return Response(str({"result": text, "file": str(f)}), media_type="application/json")


# ============================================================
# Level 0 readonly OmbreBrain docs tools
# 独立只读工具注册层，不接入写入 / 模型 / nightly-diary
# ============================================================
def _register_ombre_readonly_tool(tool_name: str, tool_func):
    @mcp.tool(name=tool_name)
    async def _readonly_wrapper(arg: str = "") -> dict:
        if tool_name == "ombre_handoff_pr2_read":
            return tool_func(arg or "both")
        if tool_name in ("ombre_reference_read", "ombre_intake_batch_read"):
            return tool_func(arg)
        return tool_func()

    return _readonly_wrapper


_OMBRE_READONLY_WRAPPERS = {
    tool_name: _register_ombre_readonly_tool(tool_name, tool_func)
    for tool_name, tool_func in READONLY_TOOL_REGISTRY.items()
}


@mcp.custom_route("/api/cadence/status", methods=["GET"])
async def api_cadence_status(request):
    from starlette.responses import JSONResponse

    latest = _latest_cadence_drafts()
    return JSONResponse({
        "enabled": CADENCE_ENABLED,
        "draft_dir": CADENCE_DRAFT_DIR,
        "receipt_dir": CADENCE_RECEIPT_DIR,
        "idle_minutes": CADENCE_IDLE_MINUTES,
        "night_window": [CADENCE_NIGHT_START_HOUR, CADENCE_NIGHT_END_HOUR],
        "night_min_idle_minutes": CADENCE_NIGHT_MIN_IDLE_MINUTES,
        "deepseek_enabled": CADENCE_DEEPSEEK_ENABLED,
        "check_interval_seconds": CADENCE_CHECK_INTERVAL_SECONDS,
        "last_check_time": _cadence_last_check_time,
        "last_skip_reason": _cadence_last_skip_reason,
        "last_activity_age_seconds": round(_cadence_recent_idle_seconds(), 1),
        "last_idle_run_ts": _cadence_last_idle_run_ts,
        "last_night_run_date": _cadence_last_night_run_date,
        "last_report": _cadence_last_report,
        "latest_drafts": latest,
        "latest_receipt": _read_latest_cadence_receipt_summary(),
        "draft_only": True,
        "main_brain_write": False,
    })


@mcp.custom_route("/api/cadence/run", methods=["GET", "POST"])
async def api_cadence_run(request):
    from starlette.responses import JSONResponse

    mode = (request.query_params.get("mode", "idle") or "idle").strip().lower()
    force = (request.query_params.get("force", "0") or "0").strip().lower() in ("1", "true", "yes")
    if mode not in ("idle", "night"):
        return JSONResponse({"error": "mode must be idle or night"}, status_code=400)

    if not force:
        _mark_runtime_activity(f"cadence_manual_{mode}")
    result = await _run_cadence_pass(
        mode=mode,
        reason="manual_force_route" if force else "manual_route",
        force_deepseek=force,
    )
    return JSONResponse(result)


@mcp.custom_route("/api/logs", methods=["GET"])
async def api_logs(request):
    from starlette.responses import PlainTextResponse

    source = request.query_params.get("source", "all")
    keyword = request.query_params.get("keyword", "")
    try:
        lines = int(request.query_params.get("lines", "50"))
    except ValueError:
        lines = 50
    result = await check_logs(lines=lines, source=source, keyword=keyword)
    return PlainTextResponse(result)


@mcp.custom_route("/api/deepseek-attribution/latest", methods=["GET"])
async def api_latest_deepseek_attribution(request):
    from starlette.responses import JSONResponse

    return JSONResponse(_read_latest_deepseek_attribution_summary() or {
        "path": "",
        "called_deepseek": False,
        "status": "none",
    })


@mcp.custom_route("/api/browser-bridge/status", methods=["GET"])
async def api_browser_bridge_status(request):
    from starlette.responses import JSONResponse

    host = os.environ.get("OMBRE_BROWSER_MCP_TAILSCALE_IP", "").strip()
    port = os.environ.get("OMBRE_BROWSER_MCP_PORT", "3001").strip()
    return JSONResponse({
        "configured": bool(host),
        "target": f"http://{host}:{port}" if host else "",
        "public_sse_path": "/browser-sse/sse",
        "tailscale_auth_configured": bool(os.environ.get("TS_AUTHKEY") or os.environ.get("TAILSCALE_AUTHKEY")),
        "proxy_mode": "app_route_proxy",
    })


async def _browser_mcp_proxy(request, path: str):
    from starlette.responses import PlainTextResponse, StreamingResponse

    host = os.environ.get("OMBRE_BROWSER_MCP_TAILSCALE_IP", "").strip()
    port = os.environ.get("OMBRE_BROWSER_MCP_PORT", "3001").strip()
    if not host:
        return PlainTextResponse(
            "Browser MCP proxy is not configured: set OMBRE_BROWSER_MCP_TAILSCALE_IP.",
            status_code=503,
        )

    path = (path or "").lstrip("/")
    target_url = f"http://{host}:{port}/{path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    excluded = {"host", "content-length", "connection", "accept-encoding"}
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in excluded
    }
    body = await request.body()

    client = httpx.AsyncClient(timeout=None, trust_env=True)
    try:
        upstream_request = client.build_request(
            request.method,
            target_url,
            headers=headers,
            content=body if body else None,
        )
        upstream = await client.send(upstream_request, stream=True)
    except Exception as e:
        await client.aclose()
        return PlainTextResponse(f"Browser MCP proxy upstream error: {e}", status_code=502)

    async def stream_response():
        try:
            async for chunk in upstream.aiter_bytes():
                if path == "sse" and request.method == "GET":
                    chunk = chunk.replace(b"data: /sse?", b"data: /browser-sse/sse?")
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    response_headers = {
        key: value
        for key, value in upstream.headers.items()
        if key.lower() not in {"content-length", "connection", "transfer-encoding"}
    }
    media_type = upstream.headers.get("content-type")
    return StreamingResponse(
        stream_response(),
        status_code=upstream.status_code,
        headers=response_headers,
        media_type=media_type,
    )


@mcp.custom_route("/browser-sse/{path:path}", methods=["GET", "POST", "OPTIONS"])
async def browser_sse_proxy(request):
    return await _browser_mcp_proxy(request, request.path_params.get("path", ""))


@mcp.custom_route("/sse", methods=["GET", "POST", "OPTIONS"])
async def browser_sse_root_compat_proxy(request):
    return await _browser_mcp_proxy(request, "sse")


async def _dual_cadence_loop():
    global _cadence_last_check_time, _cadence_last_skip_reason

    await asyncio.sleep(20)
    while True:
        try:
            if CADENCE_ENABLED:
                now_cst = clock_now()
                quiet_seconds = _cadence_recent_idle_seconds()
                quiet_minutes = round(quiet_seconds / 60, 1)
                in_night_window = _cadence_is_night_window(now_cst)
                night_gate_open = in_night_window and quiet_seconds >= (CADENCE_NIGHT_MIN_IDLE_MINUTES * 60)
                idle_gate_open = quiet_seconds >= (CADENCE_IDLE_MINUTES * 60)
                gate_open = night_gate_open or idle_gate_open
                skip_reason = "not_skipped"

                if night_gate_open and _cadence_last_night_run_date != now_cst.strftime("%Y-%m-%d"):
                    await _run_cadence_pass(mode="night", reason="night_window")
                elif idle_gate_open and _cadence_last_idle_run_ts < _cadence_last_activity_ts:
                    await _run_cadence_pass(mode="idle", reason="idle_window")
                else:
                    if in_night_window and not night_gate_open:
                        skip_reason = "night_idle_gate_closed"
                    elif in_night_window and _cadence_last_night_run_date == now_cst.strftime("%Y-%m-%d"):
                        skip_reason = "night_already_ran_today"
                    elif not idle_gate_open:
                        skip_reason = "idle_gate_closed"
                    else:
                        skip_reason = "idle_already_ran_for_current_activity"

                _cadence_last_check_time = now_cst.isoformat()
                _cadence_last_skip_reason = skip_reason
                _append_cadence_log([
                    f"[{now_cst.strftime('%Y-%m-%d %H:%M:%S')}] scheduler_check "
                    f"quiet_minutes={quiet_minutes} "
                    f"night_window={in_night_window} "
                    f"gate_open={gate_open} "
                    f"skip_reason={skip_reason} "
                    f"deepseek_enabled={CADENCE_DEEPSEEK_ENABLED}",
                ])
            else:
                now_cst = clock_now()
                _cadence_last_check_time = now_cst.isoformat()
                _cadence_last_skip_reason = "cadence_disabled"
                _append_cadence_log([
                    f"[{now_cst.strftime('%Y-%m-%d %H:%M:%S')}] scheduler_check "
                    "quiet_minutes=0.0 night_window=False gate_open=False "
                    f"skip_reason=cadence_disabled deepseek_enabled={CADENCE_DEEPSEEK_ENABLED}",
                ])
        except Exception as e:
            now_cst = clock_now()
            _cadence_last_check_time = now_cst.isoformat()
            _cadence_last_skip_reason = f"error:{e}"
            _append_cadence_log([
                f"[{now_cst.strftime('%Y-%m-%d %H:%M:%S')}] scheduler_check "
                "quiet_minutes=0.0 night_window=False gate_open=False "
                f"skip_reason=error:{e} deepseek_enabled={CADENCE_DEEPSEEK_ENABLED}",
            ])
            logger.warning(f"Dual cadence loop skipped / 双节奏循环跳过: {e}")

        await asyncio.sleep(CADENCE_CHECK_INTERVAL_SECONDS)


# --- Entry point / 启动入口 ---
if __name__ == "__main__":
    transport = config.get("transport", "stdio")
    logger.info(f"Ombre Brain starting | transport: {transport}")

    if transport in ("sse", "streamable-http"):
        async def _remote_warmup_once():
            await asyncio.sleep(1.5)
            await _wait_for_runtime_ready(max_wait_seconds=8.0)

        import threading

        def _start_remote_warmup():
            loop = asyncio.new_event_loop()
            loop.run_until_complete(_remote_warmup_once())

        warmup_thread = threading.Thread(target=_start_remote_warmup, daemon=True)
        warmup_thread.start()

    # --- Application-level keepalive: remote mode only, ping /health every 60s ---
    # --- 应用层保活：仅远程模式下启动，每 60 秒 ping 一次 /health ---
    # Prevents Cloudflare Tunnel from dropping idle connections
    if transport in ("sse", "streamable-http"):
        async def _keepalive_loop():
            await asyncio.sleep(10)  # Wait for server to fully start
            async with httpx.AsyncClient() as client:
                while True:
                    try:
                        await client.get(f"http://localhost:{int(os.environ.get('PORT', 8000))}/health", timeout=5)
                        logger.debug("Keepalive ping OK / 保活 ping 成功")
                    except Exception as e:
                        logger.warning(f"Keepalive ping failed / 保活 ping 失败: {e}")
                    await asyncio.sleep(60)

        import threading

        def _start_keepalive():
            loop = asyncio.new_event_loop()
            loop.run_until_complete(_keepalive_loop())

        t = threading.Thread(target=_start_keepalive, daemon=True)
        t.start()

    if transport in ("sse", "streamable-http") and CADENCE_ENABLED:
        def _start_dual_cadence():
            loop = asyncio.new_event_loop()
            loop.run_until_complete(_dual_cadence_loop())

        cadence_thread = threading.Thread(target=_start_dual_cadence, daemon=True)
        cadence_thread.start()

    mcp.run(transport=transport)



@mcp.custom_route("/api/test-pulse", methods=["GET"])
async def api_test_pulse(request):
    include_archive = request.query_params.get("include_archive", "false").lower() == "true"
    result = await pulse(include_archive=include_archive)
    return Response(str({"result": result}), media_type="application/json")
