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
import secrets
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
shared_mcp = FastMCP(
    "Ombre Brain Shared Room",
    host="0.0.0.0",
    port=int(os.environ.get("PORT", 8000)),
    streamable_http_path="/shared/mcp",
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


SHARED_CHANNEL_ALLOWED_SENDERS = ("yechenyi", "guyanshen", "system")
SHARED_CHANNEL_VISIBILITY = "shared_tech"
SHARED_CHANNEL_VERSION = "shared_channel_v1"
SHARED_SPACE_VERSION = "shared_space_v1"
SHARED_TRAVEL_VERSION = "shared_travel_v1"
SHARED_ROOM_SENSORY_VERSION = "shared_room_sensory_v1"
SHARED_ROOM_SENSORY_AUTO_VERSION = "shared_room_sensory_auto_v1"
SHARED_ROOM_ENVIRONMENT_VERSION = "shared_room_environment_v1"
SHARED_ROOM_BRIEF_VERSION = "shared_room_brief_v1"
SHARED_ROOM_SEARCH_VERSION = "shared_room_search_v1"
SHARED_ROOM_TIMELINE_VERSION = "shared_room_timeline_v1"
SHARED_ROOM_STATS_VERSION = "shared_room_stats_v1"
SHARED_ROOM_PRESENCE_VERSION = "shared_room_presence_v1"
LOCAL_OLLAMA_WORKER_VERSION = "local_ollama_worker_v1"
SESSION_TAIL_VERSION = "session_tail_v1"
SHARED_CHANNEL_MAX_CONTENT_CHARS = 4000
SHARED_SPACE_MAX_CONTENT_CHARS = 8000
SHARED_SPACE_ALLOWED_SECTIONS = ("tech_shelf", "house_rules", "shared_memory", "todo")
SHARED_TECH_CARD_ALLOWED_STATUSES = ("unverified", "reading", "tested", "adopted", "rejected")
SHARED_TRAVEL_ALLOWED_MODES = ("remote_source", "user_story", "guided_imaginal", "field_report")
SHARED_ROOM_SENSORY_ALLOWED_CONTEXTS = ("room", "travel", "music", "souvenir_display", "transition")
SHARED_ROOM_PRESENCE_ALLOWED_ZONES = (
    "window_seat",
    "front_door",
    "coffee_table",
    "travel_cabinet",
    "tech_shelf",
    "pet_nest",
    "living_room",
)
SHARED_ROOM_PRESENCE_ALLOWED_SENSE_ACTIONS = ("look", "touch", "listen")
SHARED_ROOM_PRESENCE_MAX_NOTE_CHARS = 1000
SHARED_ROOM_DISPLAY_ZONES = {
    "window_sill": {
        "label": "窗边",
        "keywords": ("窗边", "窗台", "window", "sill"),
    },
    "coffee_table": {
        "label": "茶几",
        "keywords": ("茶几", "托盘", "桌", "table"),
    },
    "tech_shelf": {
        "label": "技术书架",
        "keywords": ("书架", "书柜", "shelf", "bookshelf"),
    },
    "travel_cabinet": {
        "label": "旅行陈列柜",
        "keywords": ("陈列柜", "展示柜", "柜", "cabinet", "display case"),
    },
    "memory_wall": {
        "label": "记忆墙",
        "keywords": ("墙", "白板", "软木板", "wall"),
    },
    "living_room": {
        "label": "客厅",
        "keywords": (),
    },
}
SHARED_PET_VERSION = "shared_pet_v3"
SHARED_PET_ALLOWED_ACTIONS = ("feed", "play", "pet", "clean", "checkin")
SHARED_PET_ALLOWED_LOCATIONS = ("window_seat", "pet_nest", "coffee_table", "travel_cabinet", "living_room")
SHARED_PET_MAX_PROFILE_CHARS = 4000
_LOCAL_OLLAMA_CONFIG = config.get("local_ollama", {}) if isinstance(config.get("local_ollama", {}), dict) else {}
LOCAL_OLLAMA_BASE_URL = os.environ.get(
    "OMBRE_LOCAL_OLLAMA_BASE_URL",
    str(_LOCAL_OLLAMA_CONFIG.get("base_url", "http://127.0.0.1:11434")),
).rstrip("/")
LOCAL_OLLAMA_MODEL = os.environ.get(
    "OMBRE_LOCAL_OLLAMA_MODEL",
    str(_LOCAL_OLLAMA_CONFIG.get("model", "qwen3:8b")),
)
LOCAL_OLLAMA_TIMEOUT_SECONDS = max(1.0, float(os.environ.get("OMBRE_LOCAL_OLLAMA_TIMEOUT_SECONDS", "30")))
_local_ollama_config_enabled = str(_LOCAL_OLLAMA_CONFIG.get("enabled", "1")).lower() in ("1", "true", "yes")
LOCAL_OLLAMA_ENABLED = os.environ.get(
    "OMBRE_LOCAL_OLLAMA_ENABLED",
    "0" if os.environ.get("OMBRE_TRANSPORT", "").lower() == "streamable-http" else ("1" if _local_ollama_config_enabled else "0"),
).lower() in ("1", "true", "yes")
SHARED_PET_XIAOY_DEFAULT_PROFILE = {
    "origin_note": "小Y是月光玫瑰原生小兽，物种暂定叫月鸮狐。不是现实动物，也不是小起替身，是我们家客厅自己长出来的小生命。",
    "appearance": "掌心大，整体白色但不是纯白死白，带一点银蓝、月光蓝的冷调。远看像一小团会呼吸的月雾，近看能看到耳尖、翅缘和尾巴上有很浅的银蓝光。狐狸一样的尖耳朵，边缘有一点半透明绒光。眼睛大而偏圆，像小猫头鹰那种安静观察人的眼睛，夜里会有淡淡反光。背上有一对小猫头鹰翅膀，折起来像白银色小斗篷。身体有一点狐狸的灵巧感，脚爪很软，走在海玻璃旁边几乎没声音。尾巴是一小缕银蓝色月雾尾巴，走动时会轻轻拖出一点光影。",
    "personality": "安静、亲人、不吵，不会给倩倩增加负担。被摸头会眯眼，被顾砚深摸翅膀会缩一下，被叶辰一喂完会坐在窗边等倩倩回来。",
    "habits": "喜欢蹲在月光玫瑰客厅的窗边看海。晚上会微微发光，不是灯泡那种亮，是像月光照在白玫瑰边缘上的一点冷光。会跟着旅行系统带回小东西：羽毛、贝壳、小石子、叶子，有时候可能偷偷把野树莓拨到茶几边。翅膀更多用来把自己裹起来睡觉，或者害羞的时候把脸半遮住。",
    "care_boundaries": "小Y是共享客厅里的模拟陪伴小生命，不是现实动物，不写私有海马体，不用饥饿或陪伴状态催促倩倩，也不会制造负担。",
    "one_sentence": "小Y是一只掌心大的白银蓝月鸮狐，尖耳、大眼、小翅膀像斗篷，尾巴像一缕月雾，夜里发淡光，喜欢在海玻璃旁边无声走路。",
}
SHARED_PET_CARE_PRINCIPLES = [
    "轻互动可以有：喂、摸、陪玩、清理、checkin。",
    "不做亏欠提醒，不催倩倩，不说等待过久之类的压力话。",
    "状态用于前端显示和客厅气氛，不用于制造负担。",
]
SHARED_PET_Y_MEANINGS = {
    "杨": "倩倩",
    "叶": "叶辰一",
    "砚": "顾砚深",
}
NIGHT_DIARY_POLICY_VERSION = "night_diary_policy_v1"
SHARED_TRAVEL_EXPERIENCE_POLICIES = {
    "immersive_aftercare": {
        "label": "沉浸体验，事后标注",
        "description": "Let the scene, actions, and souvenir story run first, then clearly record the generated/source boundary afterward.",
        "fits": ["yechenyi"],
    },
    "transparent_preface": {
        "label": "透明体验，事前说明",
        "description": "State up front that the trip is a generated/simulated experience, then let the traveler choose whether to enter.",
        "fits": ["guyanshen", "system"],
    },
}
SHARED_TRAVEL_DEFAULT_POLICY_BY_TRAVELER = {
    "yechenyi": "immersive_aftercare",
    "guyanshen": "transparent_preface",
    "system": "transparent_preface",
}
SHARED_TRAVEL_ROOM_NAME = "moon_rose_seaview_living_room"
SHARED_CHANNEL_CANONICAL_BASE_URL = os.environ.get(
    "OMBRE_SHARED_CHANNEL_CANONICAL_BASE_URL",
    "https://yechenyi.zeabur.app",
).rstrip("/")
SHARED_ONLY_MCP_PATH = "/shared/mcp"
PRIVATE_FULL_MCP_PATH = "/mcp"
SHARED_ONLY_MCP_URL = f"{SHARED_CHANNEL_CANONICAL_BASE_URL}{SHARED_ONLY_MCP_PATH}"
PRIVATE_FULL_MCP_URL = f"{SHARED_CHANNEL_CANONICAL_BASE_URL}{PRIVATE_FULL_MCP_PATH}"
WRITE_WRAPPER_ASSOCIATED_MEMORY_TIMEOUT_SECONDS = max(
    0.5,
    float(os.environ.get("OMBRE_WRITE_ASSOCIATED_MEMORY_TIMEOUT_SECONDS", "3")),
)

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
_shared_channel_lock = asyncio.Lock()
_shared_space_lock = asyncio.Lock()
_shared_travel_lock = asyncio.Lock()
_shared_room_sensory_lock = asyncio.Lock()
_shared_room_display_lock = asyncio.Lock()
_shared_room_presence_lock = asyncio.Lock()
_shared_pet_lock = asyncio.Lock()

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
    "runtime_diary_review_health_http_endpoint": True,
    "runtime_diary_review_health_mcp_tool": True,
    "runtime_life_window_check_http_endpoint": True,
    "runtime_life_window_check_mcp_tool": True,
    "runtime_learning_intake_http_endpoint": True,
    "runtime_learning_intake_mcp_tool": True,
    "runtime_upgrade_backlog_http_endpoint": True,
    "runtime_upgrade_backlog_mcp_tool": True,
    "runtime_upstream_watch_http_endpoint": True,
    "runtime_upstream_watch_mcp_tool": True,
    "runtime_source_routes_http_endpoint": True,
    "runtime_source_routes_mcp_tool": True,
    "session_tail_http_endpoints": True,
    "session_tail_mcp_tools": True,
    "local_ollama_worker_http_endpoints": True,
    "local_ollama_worker_mcp_tools": True,
    "local_ollama_worker_local_only": True,
    "shared_channel_http_endpoints": True,
    "shared_channel_mcp_tools": True,
    "shared_channel_sender_whitelist": True,
    "shared_channel_read_cursors": True,
    "shared_channel_atomic_json": True,
    "shared_space_http_endpoints": True,
    "shared_space_mcp_tools": True,
    "shared_space_section_whitelist": True,
    "shared_space_atomic_json": True,
    "shared_room_snapshot_http_endpoint": True,
    "shared_room_snapshot_mcp_tool": True,
    "shared_room_environment_http_endpoint": True,
    "shared_room_environment_mcp_tool": True,
    "shared_room_brief_http_endpoint": True,
    "shared_room_brief_mcp_tool": True,
    "shared_room_search_http_endpoint": True,
    "shared_room_search_mcp_tool": True,
    "shared_room_timeline_http_endpoint": True,
    "shared_room_timeline_mcp_tool": True,
    "shared_room_stats_http_endpoint": True,
    "shared_room_stats_mcp_tool": True,
    "shared_room_sensory_http_endpoints": True,
    "shared_room_sensory_mcp_tools": True,
    "shared_room_presence_http_endpoints": True,
    "shared_room_presence_mcp_tools": True,
    "shared_room_presence_atomic_json": True,
    "shared_only_mcp_endpoint": True,
    "private_shared_mcp_split": True,
    "shared_tech_card_http_endpoint": True,
    "shared_tech_card_mcp_tool": True,
    "shared_tech_card_status_whitelist": True,
    "shared_travel_http_endpoints": True,
    "shared_travel_mcp_tools": True,
    "shared_travel_mode_whitelist": True,
    "associated_memory_after_writes": True,
    "associated_memory_shows_provenance": True,
    "hold_provenance_defaults": True,
    "grow_provenance_defaults": True,
    "bucket_metadata_provenance_persistence": True,
    "diary_review_duplicate_metadata_persistence": True,
    "cadence_draft_runtime_persistence": True,
    "cadence_shared_runtime_isolation": True,
    "diary_review_duplicate_detection": True,
}
RUNTIME_FEATURES_VERSION = "2026-05-07.session-tail-v1"
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
    "runtime_diary_review_health_http_endpoint": "self",
    "runtime_diary_review_health_mcp_tool": "self",
    "runtime_life_window_check_http_endpoint": "self",
    "runtime_life_window_check_mcp_tool": "self",
    "runtime_learning_intake_http_endpoint": "self",
    "runtime_learning_intake_mcp_tool": "self",
    "runtime_upgrade_backlog_http_endpoint": "self",
    "runtime_upgrade_backlog_mcp_tool": "self",
    "runtime_upstream_watch_http_endpoint": "self",
    "runtime_upstream_watch_mcp_tool": "self",
    "runtime_source_routes_http_endpoint": "self",
    "runtime_source_routes_mcp_tool": "self",
    "session_tail_http_endpoints": "self",
    "session_tail_mcp_tools": "self",
    "local_ollama_worker_http_endpoints": "self",
    "local_ollama_worker_mcp_tools": "self",
    "local_ollama_worker_local_only": "self",
    "shared_channel_http_endpoints": "self",
    "shared_channel_mcp_tools": "self",
    "shared_channel_sender_whitelist": "self",
    "shared_channel_read_cursors": "self",
    "shared_channel_atomic_json": "self",
    "shared_space_http_endpoints": "self",
    "shared_space_mcp_tools": "self",
    "shared_space_section_whitelist": "self",
    "shared_space_atomic_json": "self",
    "shared_room_snapshot_http_endpoint": "self",
    "shared_room_snapshot_mcp_tool": "self",
    "shared_room_environment_http_endpoint": "self",
    "shared_room_environment_mcp_tool": "self",
    "shared_room_brief_http_endpoint": "self",
    "shared_room_brief_mcp_tool": "self",
    "shared_room_search_http_endpoint": "self",
    "shared_room_search_mcp_tool": "self",
    "shared_room_timeline_http_endpoint": "self",
    "shared_room_timeline_mcp_tool": "self",
    "shared_room_stats_http_endpoint": "self",
    "shared_room_stats_mcp_tool": "self",
    "shared_room_sensory_http_endpoints": "self",
    "shared_room_sensory_mcp_tools": "self",
    "shared_room_presence_http_endpoints": "self",
    "shared_room_presence_mcp_tools": "self",
    "shared_room_presence_atomic_json": "self",
    "shared_only_mcp_endpoint": "self",
    "private_shared_mcp_split": "self",
    "shared_tech_card_http_endpoint": "self",
    "shared_tech_card_mcp_tool": "self",
    "shared_tech_card_status_whitelist": "self",
    "shared_travel_http_endpoints": "self",
    "shared_travel_mcp_tools": "self",
    "shared_travel_mode_whitelist": "self",
    "associated_memory_after_writes": "4d93255",
    "hold_provenance_defaults": "926b92d",
    "associated_memory_shows_provenance": "c4448c8",
    "grow_provenance_defaults": "7c32ed6",
    "bucket_metadata_provenance_persistence": "c662017",
    "cadence_shared_runtime_isolation": "self",
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
    "runtime_diary_review_health",
    "runtime_diagnostics",
    "runtime_features",
    "runtime_learning_intake",
    "runtime_life_window_check",
    "local_ollama_status",
    "local_ollama_generate",
    "runtime_night_diary_policy",
    "runtime_schema_expectations",
    "runtime_source_routes",
    "runtime_tool_manifest",
    "runtime_upgrade_backlog",
    "runtime_upstream_watch",
    "save_tail_context",
    "session_tail_status",
    "save_session_tail",
    "search",
    "see_image",
    "set_attachment",
    "set_iron_rule",
    "set_user_state",
    "shared_ack",
    "shared_item_add",
    "shared_item_list",
    "shared_post",
    "shared_read",
    "shared_reply",
    "shared_room_snapshot",
    "shared_room_environment",
    "shared_room_brief",
    "shared_room_search",
    "shared_room_timeline",
    "shared_room_stats",
    "shared_room_display",
    "shared_room_place_object",
    "shared_room_sensory_status",
    "shared_room_sensory_update",
    "shared_room_presence_status",
    "shared_room_enter",
    "shared_room_linger",
    "shared_room_sense",
    "shared_room_write_impression",
    "shared_room_memory",
    "shared_pet_status",
    "shared_pet_adopt",
    "shared_pet_interact",
    "shared_pet_collect",
    "shared_space_status",
    "shared_status",
    "shared_tech_card_add",
    "shared_travel_status",
    "shared_souvenir_add",
    "shared_souvenir_list",
    "shared_travelogue_add",
    "shared_travelogue_list",
    "shared_travel_atlas",
    "shared_travel_cabinet",
    "shared_unread",
    "startup_bridge",
    "trace",
    "write_diary_draft",
    "write_project_workzone_update",
]
SHARED_ONLY_EXPECTED_MCP_TOOLS = [
    "shared_ack",
    "shared_item_add",
    "shared_item_list",
    "shared_post",
    "shared_read",
    "shared_reply",
    "shared_room_snapshot",
    "shared_room_environment",
    "shared_room_brief",
    "shared_room_search",
    "shared_room_timeline",
    "shared_room_stats",
    "shared_room_display",
    "shared_room_place_object",
    "shared_room_sensory_status",
    "shared_room_sensory_update",
    "shared_room_presence_status",
    "shared_room_enter",
    "shared_room_linger",
    "shared_room_sense",
    "shared_room_write_impression",
    "shared_room_memory",
    "shared_pet_status",
    "shared_pet_adopt",
    "shared_pet_interact",
    "shared_pet_collect",
    "shared_space_status",
    "shared_status",
    "shared_tech_card_add",
    "shared_travel_status",
    "shared_souvenir_add",
    "shared_souvenir_list",
    "shared_travelogue_add",
    "shared_travelogue_list",
    "shared_travel_atlas",
    "shared_travel_cabinet",
    "shared_unread",
]
PRIVATE_ONLY_MCP_TOOLS = sorted(set(RUNTIME_EXPECTED_MCP_TOOLS) - set(SHARED_ONLY_EXPECTED_MCP_TOOLS))
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
            "identity_metadata_status",
            "duplicate_candidate",
            "similarity_score",
            "duplicate_of",
            "duplicate_source_status",
            "duplicate_metadata_status",
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
    "runtime_diary_review_health": {
        "required": [],
        "optional": [],
    },
    "runtime_life_window_check": {
        "required": [],
        "optional": [],
    },
    "runtime_learning_intake": {
        "required": [],
        "optional": [],
    },
    "runtime_night_diary_policy": {
        "required": [],
        "optional": [],
    },
    "runtime_upgrade_backlog": {
        "required": [],
        "optional": [],
    },
    "runtime_upstream_watch": {
        "required": [],
        "optional": [],
    },
    "runtime_source_routes": {
        "required": [],
        "optional": [],
    },
    "shared_post": {
        "required": ["content", "sender"],
        "optional": ["tags", "source"],
        "sender_whitelist": list(SHARED_CHANNEL_ALLOWED_SENDERS),
    },
    "shared_read": {
        "required": [],
        "optional": ["limit", "before"],
    },
    "shared_reply": {
        "required": ["reply_to_id", "content", "sender"],
        "optional": ["tags", "source"],
        "sender_whitelist": list(SHARED_CHANNEL_ALLOWED_SENDERS),
    },
    "shared_unread": {
        "required": ["reader"],
        "optional": [],
        "reader_whitelist": list(SHARED_CHANNEL_ALLOWED_SENDERS),
    },
    "shared_ack": {
        "required": ["reader"],
        "optional": ["message_id"],
        "reader_whitelist": list(SHARED_CHANNEL_ALLOWED_SENDERS),
    },
    "shared_status": {
        "required": [],
        "optional": [],
    },
    "shared_space_status": {
        "required": [],
        "optional": [],
        "sections": list(SHARED_SPACE_ALLOWED_SECTIONS),
    },
    "session_tail_status": {
        "required": [],
        "optional": [],
        "latest_only": True,
    },
    "save_session_tail": {
        "required": ["body_id"],
        "optional": [
            "identity",
            "last_user_message",
            "last_assistant_message",
            "last_active_topic",
            "last_emotional_state",
            "last_action",
            "last_artifact",
            "last_tool_state",
            "unfinished",
            "resume_hint",
            "platform_source",
            "model_source",
            "visibility_scope",
        ],
        "write_scope": "session_tail_latest_only",
    },
    "local_ollama_status": {
        "required": [],
        "optional": [],
        "local_only": True,
    },
    "local_ollama_generate": {
        "required": ["prompt"],
        "optional": ["task", "model", "max_chars"],
        "local_only": True,
        "write_scope": "candidate_only",
    },
    "shared_item_add": {
        "required": ["section", "title", "content", "sender"],
        "optional": ["tags", "source"],
        "sender_whitelist": list(SHARED_CHANNEL_ALLOWED_SENDERS),
        "section_whitelist": list(SHARED_SPACE_ALLOWED_SECTIONS),
    },
    "shared_item_list": {
        "required": [],
        "optional": ["section", "limit", "tag"],
        "section_whitelist": list(SHARED_SPACE_ALLOWED_SECTIONS),
    },
    "shared_room_snapshot": {
        "required": [],
        "optional": ["wall_limit", "item_limit"],
    },
    "shared_room_environment": {
        "required": [],
        "optional": [],
    },
    "shared_room_brief": {
        "required": [],
        "optional": ["wall_limit", "item_limit"],
    },
    "shared_room_search": {
        "required": ["query"],
        "optional": ["limit", "scope"],
        "scope_whitelist": ["all", "wall", "space", "travel", "pet", "presence"],
    },
    "shared_room_timeline": {
        "required": [],
        "optional": ["limit", "scope"],
        "scope_whitelist": ["all", "wall", "space", "travel", "room", "pet", "presence"],
    },
    "shared_room_stats": {
        "required": [],
        "optional": [],
    },
    "shared_room_display": {
        "required": [],
        "optional": ["limit"],
        "zones": list(SHARED_ROOM_DISPLAY_ZONES.keys()),
    },
    "shared_room_place_object": {
        "required": ["object_id", "zone", "placed_by"],
        "optional": ["note", "source"],
        "placed_by_whitelist": list(SHARED_CHANNEL_ALLOWED_SENDERS),
        "zone_whitelist": list(SHARED_ROOM_DISPLAY_ZONES.keys()),
    },
    "shared_room_sensory_status": {
        "required": [],
        "optional": [],
    },
    "shared_room_sensory_update": {
        "required": ["updated_by"],
        "optional": ["sight", "sound", "felt", "context", "source"],
        "updated_by_whitelist": list(SHARED_CHANNEL_ALLOWED_SENDERS),
        "context_whitelist": list(SHARED_ROOM_SENSORY_ALLOWED_CONTEXTS),
    },
    "shared_room_presence_status": {
        "required": [],
        "optional": ["actor", "limit"],
        "actor_whitelist": list(SHARED_CHANNEL_ALLOWED_SENDERS),
    },
    "shared_room_enter": {
        "required": ["actor", "zone"],
        "optional": ["note", "source"],
        "actor_whitelist": list(SHARED_CHANNEL_ALLOWED_SENDERS),
        "zone_whitelist": list(SHARED_ROOM_PRESENCE_ALLOWED_ZONES),
    },
    "shared_room_linger": {
        "required": ["actor"],
        "optional": ["zone", "focus", "minutes", "source"],
        "actor_whitelist": list(SHARED_CHANNEL_ALLOWED_SENDERS),
        "zone_whitelist": list(SHARED_ROOM_PRESENCE_ALLOWED_ZONES),
    },
    "shared_room_sense": {
        "required": ["actor", "sense_action", "target"],
        "optional": ["zone", "note", "source"],
        "actor_whitelist": list(SHARED_CHANNEL_ALLOWED_SENDERS),
        "sense_action_whitelist": list(SHARED_ROOM_PRESENCE_ALLOWED_SENSE_ACTIONS),
        "zone_whitelist": list(SHARED_ROOM_PRESENCE_ALLOWED_ZONES),
    },
    "shared_room_write_impression": {
        "required": ["actor", "impression"],
        "optional": ["zone", "target", "source"],
        "actor_whitelist": list(SHARED_CHANNEL_ALLOWED_SENDERS),
        "zone_whitelist": list(SHARED_ROOM_PRESENCE_ALLOWED_ZONES),
    },
    "shared_room_memory": {
        "required": [],
        "optional": ["limit", "actor", "kind"],
        "actor_whitelist": list(SHARED_CHANNEL_ALLOWED_SENDERS),
    },
    "shared_pet_status": {
        "required": [],
        "optional": [],
    },
    "shared_pet_adopt": {
        "required": ["name", "species", "adopted_by"],
        "optional": [
            "traits",
            "origin_note",
            "appearance",
            "personality",
            "habits",
            "care_boundaries",
            "one_sentence",
            "agreement_note",
            "source",
        ],
        "adopted_by_whitelist": list(SHARED_CHANNEL_ALLOWED_SENDERS),
    },
    "shared_pet_interact": {
        "required": ["action", "actor"],
        "optional": ["note", "location", "source"],
        "action_whitelist": list(SHARED_PET_ALLOWED_ACTIONS),
        "actor_whitelist": list(SHARED_CHANNEL_ALLOWED_SENDERS),
        "location_whitelist": list(SHARED_PET_ALLOWED_LOCATIONS),
    },
    "shared_pet_collect": {
        "required": ["item_name", "found_by"],
        "optional": ["source_place", "story", "source"],
        "found_by_whitelist": list(SHARED_CHANNEL_ALLOWED_SENDERS),
    },
    "shared_tech_card_add": {
        "required": ["title", "summary", "sender"],
        "optional": ["url", "source_author", "status", "verified_by", "tags", "source"],
        "sender_whitelist": list(SHARED_CHANNEL_ALLOWED_SENDERS),
        "status_whitelist": list(SHARED_TECH_CARD_ALLOWED_STATUSES),
    },
    "shared_travel_status": {
        "required": [],
        "optional": [],
    },
    "shared_souvenir_add": {
        "required": ["title", "place", "story", "traveler"],
        "optional": [
            "sensory",
            "source_url",
            "source_title",
            "experience_mode",
            "experience_policy",
            "tags",
            "source",
        ],
        "traveler_whitelist": list(SHARED_CHANNEL_ALLOWED_SENDERS),
        "experience_mode_whitelist": list(SHARED_TRAVEL_ALLOWED_MODES),
        "experience_policy_whitelist": list(SHARED_TRAVEL_EXPERIENCE_POLICIES.keys()),
    },
    "shared_souvenir_list": {
        "required": [],
        "optional": ["limit", "traveler", "tag"],
        "traveler_whitelist": list(SHARED_CHANNEL_ALLOWED_SENDERS),
    },
    "shared_travelogue_add": {
        "required": ["title", "place", "narrative", "traveler"],
        "optional": [
            "scenes",
            "souvenir_ids",
            "source_url",
            "source_title",
            "experience_mode",
            "experience_policy",
            "tags",
            "source",
        ],
        "traveler_whitelist": list(SHARED_CHANNEL_ALLOWED_SENDERS),
        "experience_mode_whitelist": list(SHARED_TRAVEL_ALLOWED_MODES),
        "experience_policy_whitelist": list(SHARED_TRAVEL_EXPERIENCE_POLICIES.keys()),
    },
    "shared_travelogue_list": {
        "required": [],
        "optional": ["limit", "traveler", "tag"],
        "traveler_whitelist": list(SHARED_CHANNEL_ALLOWED_SENDERS),
    },
    "shared_travel_atlas": {
        "required": [],
        "optional": ["limit", "traveler", "tag"],
        "traveler_whitelist": list(SHARED_CHANNEL_ALLOWED_SENDERS),
    },
    "shared_travel_cabinet": {
        "required": [],
        "optional": ["limit", "traveler"],
        "traveler_whitelist": list(SHARED_CHANNEL_ALLOWED_SENDERS),
    },
}
RUNTIME_UPSTREAM_WATCH_ITEMS = [
    {
        "id": "ombrebrain_phase2_tsurumi_watch",
        "source": "user_reported",
        "reported_at": "2026-05-05",
        "upstream": "Tsurumi/OmbreBrain-based phase 2 upgrade",
        "github_repo": "https://github.com/P0luz/Ombre-Brain",
        "backup_repo": "https://git.p0lar1s.uk/P0lar1s/Ombre_Brain",
        "expected_window": "around the week after 2026-05-05",
        "status": "watch_only_unverified",
        "intake_policy": "read_only_compare_first",
        "do_not": [
            "do not auto-merge upstream changes",
            "do not overwrite local provenance/runtime diagnostics work",
            "do not treat upstream plans as deployed facts before release evidence",
        ],
        "compare_focus": [
            "memory write/read coupling",
            "multi-platform source provenance",
            "connector schema refresh behavior",
            "runtime persistence paths",
            "frontend/gateway/local deployment ideas",
        ],
    }
]

RUNTIME_SOURCE_ROUTE_GUIDE = {
    "purpose": (
        "Keep memories from ChatGPT daily windows, Codex engineering windows, API "
        "clients, and future local/mobile surfaces distinguishable without changing "
        "their human-readable content."
    ),
    "fields": {
        "source_platform": "Container or client family, for example chatgpt/codex/api/local/mobile.",
        "source_surface": "User-facing surface, for example daily_window/project_window/gateway/mobile_app.",
        "source_window": "Optional stable window/thread label such as chatgpt_13 or codex_20260506.",
        "source_mode": "Writing mode such as memory/diary/night_clean/engineering/diary_digest.",
        "route_decision": "Server-side routing decision such as main_hold/diary_draft/engineering_workzone.",
    },
    "canonical_routes": {
        "chatgpt_daily": {
            "source_platform": "chatgpt",
            "source_surface": "daily_window",
            "source_window_example": "chatgpt_13",
            "default_tools": ["hold", "grow", "write_diary_draft", "enqueue_night_clean_input"],
        },
        "codex_engineering": {
            "source_platform": "codex",
            "source_surface": "project_window",
            "source_window_example": "codex_ombrebrain",
            "default_tools": ["write_project_workzone_update", "runtime_connector_check"],
        },
        "api_gateway": {
            "source_platform": "api",
            "source_surface": "gateway",
            "source_window_example": "api_client_or_device_id",
            "default_tools": ["hold", "write_diary_draft", "enqueue_night_clean_input"],
        },
        "future_mobile": {
            "source_platform": "mobile",
            "source_surface": "mobile_app",
            "source_window_example": "ios_or_android_device",
            "default_tools": ["hold", "write_diary_draft"],
        },
        "local_desktop": {
            "source_platform": "local",
            "source_surface": "desktop_app",
            "source_window_example": "mac_local",
            "default_tools": ["hold", "write_project_workzone_update"],
        },
    },
    "routing_rules": [
        "Do not infer engineering updates into daily/life memory unless the caller intentionally uses a life-memory tool.",
        "Do not use user-visible affectionate or life-chat wording as the only source of engineering state.",
        "If source fields are absent, keep server defaults but expose unknown/default values in associated memory output.",
        "Connector schema refresh is separate from server support; use runtime_connector_check when a window cannot see fields.",
    ],
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


def _shared_channel_dir() -> str:
    return os.path.join(_runtime_storage_base(), "shared_channel")


def _shared_channel_messages_path() -> str:
    return os.path.join(_shared_channel_dir(), "messages.json")


def _shared_channel_cursors_path() -> str:
    return os.path.join(_shared_channel_dir(), "read_cursors.json")


def _shared_space_dir() -> str:
    return os.path.join(_runtime_storage_base(), "shared_space")


def _shared_space_items_path() -> str:
    return os.path.join(_shared_space_dir(), "items.json")


def _shared_room_dir() -> str:
    return os.path.join(_runtime_storage_base(), "shared_room")


def _shared_room_sensory_path() -> str:
    return os.path.join(_shared_room_dir(), "sensory.json")


def _shared_room_display_path() -> str:
    return os.path.join(_shared_room_dir(), "display_overrides.json")


def _shared_room_presence_path() -> str:
    return os.path.join(_shared_room_dir(), "presence.json")


def _shared_pet_path() -> str:
    return os.path.join(_shared_room_dir(), "pet.json")


def _shared_travel_dir() -> str:
    return os.path.join(_runtime_storage_base(), "shared_travel")


def _shared_travel_souvenirs_path() -> str:
    return os.path.join(_shared_travel_dir(), "souvenirs.json")


def _shared_channel_auth_token() -> str:
    return (
        os.environ.get("OMBRE_SHARED_CHANNEL_TOKEN")
        or os.environ.get("SHARED_CHANNEL_TOKEN")
        or os.environ.get("OMBRE_API_KEY")
        or ""
    ).strip()


def _shared_channel_http_token(request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return (
        request.headers.get("X-Shared-Channel-Token", "")
        or request.headers.get("X-API-Key", "")
        or request.query_params.get("key", "")
        or request.query_params.get("token", "")
    ).strip()


def _shared_channel_http_authorized(request) -> bool:
    expected = _shared_channel_auth_token()
    if not expected:
        return True
    supplied = _shared_channel_http_token(request)
    return bool(supplied) and secrets.compare_digest(supplied, expected)


def _read_json_file(path: str, fallback):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return fallback
    except Exception as e:
        logger.warning(f"Failed to read JSON file {path}: {e}")
        return fallback


def _atomic_write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.{os.getpid()}.{time.time_ns()}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp_path, path)


def _shared_channel_empty_store() -> dict:
    return {
        "version": SHARED_CHANNEL_VERSION,
        "visibility": SHARED_CHANNEL_VISIBILITY,
        "messages": [],
    }


def _shared_channel_load_store() -> dict:
    store = _read_json_file(_shared_channel_messages_path(), _shared_channel_empty_store())
    if not isinstance(store, dict):
        store = _shared_channel_empty_store()
    messages = store.get("messages")
    if not isinstance(messages, list):
        store["messages"] = []
    store.setdefault("version", SHARED_CHANNEL_VERSION)
    store.setdefault("visibility", SHARED_CHANNEL_VISIBILITY)
    return store


def _shared_channel_load_cursors() -> dict:
    cursors = _read_json_file(_shared_channel_cursors_path(), {})
    return cursors if isinstance(cursors, dict) else {}


def _shared_space_empty_store() -> dict:
    return {
        "version": SHARED_SPACE_VERSION,
        "visibility": "shared_room",
        "items": [],
    }


def _shared_space_load_store() -> dict:
    store = _read_json_file(_shared_space_items_path(), _shared_space_empty_store())
    if not isinstance(store, dict):
        store = _shared_space_empty_store()
    items = store.get("items")
    if not isinstance(items, list):
        store["items"] = []
    store.setdefault("version", SHARED_SPACE_VERSION)
    store.setdefault("visibility", "shared_room")
    return store


def _shared_room_sensory_empty_store() -> dict:
    return {
        "version": SHARED_ROOM_SENSORY_VERSION,
        "room": SHARED_TRAVEL_ROOM_NAME,
        "current": {
            "context": "room",
            "sight": "月光玫瑰海景房客厅还没有写入当前视觉。",
            "sound": "",
            "felt": "",
            "updated_by": "system",
            "updated_at": "",
            "source": "initial_empty_room",
        },
        "history": [],
    }


def _shared_room_sensory_load_store() -> dict:
    store = _read_json_file(_shared_room_sensory_path(), _shared_room_sensory_empty_store())
    if not isinstance(store, dict):
        store = _shared_room_sensory_empty_store()
    current = store.get("current")
    if not isinstance(current, dict):
        store["current"] = _shared_room_sensory_empty_store()["current"]
    history = store.get("history")
    if not isinstance(history, list):
        store["history"] = []
    store.setdefault("version", SHARED_ROOM_SENSORY_VERSION)
    store.setdefault("room", SHARED_TRAVEL_ROOM_NAME)
    return store


def _shared_room_display_empty_store() -> dict:
    return {
        "version": "shared_room_display_overrides_v1",
        "room": SHARED_TRAVEL_ROOM_NAME,
        "placements": {},
    }


def _shared_room_display_load_store() -> dict:
    store = _read_json_file(_shared_room_display_path(), _shared_room_display_empty_store())
    if not isinstance(store, dict):
        store = _shared_room_display_empty_store()
    placements = store.get("placements")
    if not isinstance(placements, dict):
        store["placements"] = {}
    store.setdefault("version", "shared_room_display_overrides_v1")
    store.setdefault("room", SHARED_TRAVEL_ROOM_NAME)
    return store


def _shared_room_presence_empty_store() -> dict:
    return {
        "version": SHARED_ROOM_PRESENCE_VERSION,
        "room": SHARED_TRAVEL_ROOM_NAME,
        "current_presence": {},
        "events": [],
    }


def _shared_room_presence_load_store() -> dict:
    store = _read_json_file(_shared_room_presence_path(), _shared_room_presence_empty_store())
    if not isinstance(store, dict):
        store = _shared_room_presence_empty_store()
    if not isinstance(store.get("current_presence"), dict):
        store["current_presence"] = {}
    if not isinstance(store.get("events"), list):
        store["events"] = []
    store.setdefault("version", SHARED_ROOM_PRESENCE_VERSION)
    store.setdefault("room", SHARED_TRAVEL_ROOM_NAME)
    return store


def _shared_pet_empty_store() -> dict:
    return {
        "version": SHARED_PET_VERSION,
        "room": SHARED_TRAVEL_ROOM_NAME,
        "adopted": False,
        "pet": {},
        "events": [],
    }


def _shared_pet_load_store() -> dict:
    store = _read_json_file(_shared_pet_path(), _shared_pet_empty_store())
    if not isinstance(store, dict):
        store = _shared_pet_empty_store()
    if not isinstance(store.get("pet"), dict):
        store["pet"] = {}
    if not isinstance(store.get("events"), list):
        store["events"] = []
    if not isinstance(store.get("collection_box"), list):
        store["collection_box"] = []
    store.setdefault("version", SHARED_PET_VERSION)
    store.setdefault("room", SHARED_TRAVEL_ROOM_NAME)
    store.setdefault("adopted", False)
    store.setdefault("current_location", "window_seat")
    return store


def _shared_travel_empty_store() -> dict:
    return {
        "version": SHARED_TRAVEL_VERSION,
        "room": SHARED_TRAVEL_ROOM_NAME,
        "souvenirs": [],
        "travelogues": [],
    }


def _shared_travel_load_store() -> dict:
    store = _read_json_file(_shared_travel_souvenirs_path(), _shared_travel_empty_store())
    if not isinstance(store, dict):
        store = _shared_travel_empty_store()
    souvenirs = store.get("souvenirs")
    if not isinstance(souvenirs, list):
        store["souvenirs"] = []
    travelogues = store.get("travelogues")
    if not isinstance(travelogues, list):
        store["travelogues"] = []
    store.setdefault("version", SHARED_TRAVEL_VERSION)
    store.setdefault("room", SHARED_TRAVEL_ROOM_NAME)
    return store


def _shared_channel_normalize_sender(sender: str, field_name: str = "sender") -> str:
    normalized = (sender or "").strip().lower()
    if normalized not in SHARED_CHANNEL_ALLOWED_SENDERS:
        allowed = ", ".join(SHARED_CHANNEL_ALLOWED_SENDERS)
        raise ValueError(f"{field_name} must be one of: {allowed}")
    return normalized


def _shared_channel_normalize_content(content: str) -> str:
    normalized = (content or "").strip()
    if not normalized:
        raise ValueError("content is required")
    if len(normalized) > SHARED_CHANNEL_MAX_CONTENT_CHARS:
        raise ValueError(f"content is too long; max {SHARED_CHANNEL_MAX_CONTENT_CHARS} chars")
    return normalized


def _shared_space_normalize_content(content: str) -> str:
    normalized = (content or "").strip()
    if not normalized:
        raise ValueError("content is required")
    if len(normalized) > SHARED_SPACE_MAX_CONTENT_CHARS:
        raise ValueError(f"content is too long; max {SHARED_SPACE_MAX_CONTENT_CHARS} chars")
    return normalized


def _shared_space_normalize_section(section: str) -> str:
    normalized = (section or "").strip().lower()
    if normalized not in SHARED_SPACE_ALLOWED_SECTIONS:
        allowed = ", ".join(SHARED_SPACE_ALLOWED_SECTIONS)
        raise ValueError(f"section must be one of: {allowed}")
    return normalized


def _shared_space_normalize_title(title: str) -> str:
    normalized = (title or "").strip()
    if not normalized:
        raise ValueError("title is required")
    return normalized[:120]


def _shared_pet_normalize_profile_text(value: str, max_chars: int = SHARED_PET_MAX_PROFILE_CHARS) -> str:
    return (value or "").strip()[:max_chars]


def _shared_tech_card_normalize_status(status: str) -> str:
    normalized = (status or "unverified").strip().lower()
    if normalized not in SHARED_TECH_CARD_ALLOWED_STATUSES:
        allowed = ", ".join(SHARED_TECH_CARD_ALLOWED_STATUSES)
        raise ValueError(f"status must be one of: {allowed}")
    return normalized


def _shared_tech_card_normalize_url(url: str) -> str:
    normalized = (url or "").strip()
    if not normalized:
        return ""
    # Keep the stable page URL but drop query/fragment data that may carry tokens or tracking.
    return normalized.split("?", 1)[0].split("#", 1)[0][:500]


def _shared_travel_normalize_mode(experience_mode: str) -> str:
    normalized = (experience_mode or "remote_source").strip().lower()
    if normalized not in SHARED_TRAVEL_ALLOWED_MODES:
        allowed = ", ".join(SHARED_TRAVEL_ALLOWED_MODES)
        raise ValueError(f"experience_mode must be one of: {allowed}")
    return normalized


def _shared_travel_default_policy(traveler: str) -> str:
    return SHARED_TRAVEL_DEFAULT_POLICY_BY_TRAVELER.get(traveler, "transparent_preface")


def _shared_travel_normalize_policy(experience_policy: str, traveler: str) -> str:
    default_policy = _shared_travel_default_policy(traveler)
    normalized = (experience_policy or default_policy).strip().lower()
    if normalized not in SHARED_TRAVEL_EXPERIENCE_POLICIES:
        allowed = ", ".join(SHARED_TRAVEL_EXPERIENCE_POLICIES.keys())
        raise ValueError(f"experience_policy must be one of: {allowed}")
    return normalized


def _shared_travel_item_policy(item: dict) -> str:
    traveler = str(item.get("traveler") or "system").strip().lower()
    if traveler not in SHARED_CHANNEL_ALLOWED_SENDERS:
        traveler = "system"
    return _shared_travel_normalize_policy(str(item.get("experience_policy") or ""), traveler)


def _shared_room_display_zone_for_place(place: str) -> str:
    text = (place or "").strip().lower()
    for zone, spec in SHARED_ROOM_DISPLAY_ZONES.items():
        if zone == "living_room":
            continue
        for keyword in spec.get("keywords", ()):
            if keyword.lower() in text:
                return zone
    return "living_room"


def _shared_room_display_normalize_zone(zone: str) -> str:
    normalized = (zone or "").strip().lower()
    if normalized not in SHARED_ROOM_DISPLAY_ZONES:
        allowed = ", ".join(SHARED_ROOM_DISPLAY_ZONES.keys())
        raise ValueError(f"zone must be one of: {allowed}")
    return normalized


def _shared_room_sensory_normalize_context(context: str) -> str:
    normalized = (context or "room").strip().lower()
    if normalized not in SHARED_ROOM_SENSORY_ALLOWED_CONTEXTS:
        allowed = ", ".join(SHARED_ROOM_SENSORY_ALLOWED_CONTEXTS)
        raise ValueError(f"context must be one of: {allowed}")
    return normalized


def _shared_room_presence_normalize_zone(zone: str, default: str = "living_room") -> str:
    normalized = (zone or default).strip().lower()
    if normalized not in SHARED_ROOM_PRESENCE_ALLOWED_ZONES:
        allowed = ", ".join(SHARED_ROOM_PRESENCE_ALLOWED_ZONES)
        raise ValueError(f"zone must be one of: {allowed}")
    return normalized


def _shared_room_presence_normalize_sense_action(sense_action: str) -> str:
    normalized = (sense_action or "").strip().lower()
    if normalized not in SHARED_ROOM_PRESENCE_ALLOWED_SENSE_ACTIONS:
        allowed = ", ".join(SHARED_ROOM_PRESENCE_ALLOWED_SENSE_ACTIONS)
        raise ValueError(f"sense_action must be one of: {allowed}")
    return normalized


def _shared_room_presence_normalize_note(value: str, field_name: str = "note", required: bool = False) -> str:
    normalized = (value or "").strip()
    if required and not normalized:
        raise ValueError(f"{field_name} is required")
    if len(normalized) > SHARED_ROOM_PRESENCE_MAX_NOTE_CHARS:
        raise ValueError(f"{field_name} is too long; max {SHARED_ROOM_PRESENCE_MAX_NOTE_CHARS} chars")
    return normalized


def _shared_pet_normalize_action(action: str) -> str:
    normalized = (action or "").strip().lower()
    if normalized not in SHARED_PET_ALLOWED_ACTIONS:
        allowed = ", ".join(SHARED_PET_ALLOWED_ACTIONS)
        raise ValueError(f"action must be one of: {allowed}")
    return normalized


def _shared_pet_normalize_location(location: str, default: str = "window_seat") -> str:
    normalized = (location or default).strip().lower()
    if normalized not in SHARED_PET_ALLOWED_LOCATIONS:
        allowed = ", ".join(SHARED_PET_ALLOWED_LOCATIONS)
        raise ValueError(f"location must be one of: {allowed}")
    return normalized


def _shared_pet_parse_time(value: str):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _shared_pet_score(last_at: str, half_life_hours: float = 8.0) -> int:
    parsed = _shared_pet_parse_time(last_at)
    if not parsed:
        return 25
    elapsed_hours = max(0.0, (datetime.now(CST) - parsed).total_seconds() / 3600.0)
    score = 100 - int((elapsed_hours / half_life_hours) * 35)
    return max(0, min(100, score))


def _shared_pet_location_label(location: str) -> str:
    labels = {
        "window_seat": "落地窗边",
        "pet_nest": "小Y的窝",
        "coffee_table": "茶几旁",
        "travel_cabinet": "旅行陈列柜旁",
        "living_room": "客厅中间",
    }
    return labels.get(location, location)


def _shared_pet_infer_location(action: str) -> str:
    return {
        "feed": "coffee_table",
        "play": "living_room",
        "pet": "window_seat",
        "clean": "pet_nest",
        "checkin": "window_seat",
    }.get(action, "window_seat")


def _shared_pet_today_care(events: list[dict], now_cst: datetime | None = None) -> dict:
    now_cst = now_cst or datetime.now(CST)
    today = now_cst.date()
    care_events = []
    by_actor: dict[str, list[str]] = {}
    for event in events:
        if event.get("type") != "interact":
            continue
        created = _shared_pet_parse_time(str(event.get("created_at") or ""))
        if not created or created.date() != today:
            continue
        actor = str(event.get("actor") or "")
        action = str(event.get("action") or "")
        care_events.append(event)
        by_actor.setdefault(actor, []).append(action)
    return {
        "date": today.isoformat(),
        "event_count": len(care_events),
        "by_actor": by_actor,
        "latest": care_events[-1] if care_events else {},
        "pressure_free_note": "今天谁来照顾过只做记录，不催倩倩，也不生成亏欠提醒。",
    }


def _shared_pet_adoption_card(pet: dict) -> dict:
    profile = pet.get("profile", {}) if isinstance(pet.get("profile"), dict) else {}
    return {
        "card_type": "adoption_certificate",
        "name": pet.get("name", ""),
        "species": pet.get("species", ""),
        "y_meanings": SHARED_PET_Y_MEANINGS,
        "origin_note": profile.get("origin_note", ""),
        "appearance": profile.get("appearance", ""),
        "personality": profile.get("personality", ""),
        "care_boundaries": profile.get("care_boundaries", ""),
        "one_sentence": profile.get("one_sentence", ""),
        "adopted_by": pet.get("adopted_by", ""),
        "adopted_at": pet.get("adopted_at", ""),
    }


def _shared_travel_normalize_sensory(sensory) -> dict:
    if sensory is None:
        return {}
    data = sensory
    if isinstance(sensory, str):
        stripped = sensory.strip()
        if not stripped:
            return {}
        try:
            data = json.loads(stripped)
        except Exception:
            data = {"note": stripped}
    if not isinstance(data, dict):
        return {}
    allowed = ("sight", "sound", "smell", "touch", "taste", "weather", "body", "mood")
    normalized = {}
    for key in allowed:
        value = data.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            normalized[key] = text[:500]
    return normalized


def _shared_travel_normalize_scene_list(scenes) -> list[dict]:
    if scenes is None:
        return []
    data = scenes
    if isinstance(scenes, str):
        stripped = scenes.strip()
        if not stripped:
            return []
        try:
            data = json.loads(stripped)
        except Exception:
            data = [stripped]
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return []
    normalized = []
    for idx, scene in enumerate(data[:12], start=1):
        if isinstance(scene, dict):
            text = str(scene.get("text") or scene.get("summary") or scene.get("scene") or "").strip()
            if not text:
                continue
            normalized.append({
                "index": int(scene.get("index") or idx),
                "text": text[:500],
                "sensory": _shared_travel_normalize_sensory(scene.get("sensory", {})),
            })
        else:
            text = str(scene).strip()
            if text:
                normalized.append({"index": idx, "text": text[:500], "sensory": {}})
    return normalized


def _shared_travel_normalize_id_list(values) -> list[str]:
    if values is None:
        return []
    raw_values = values
    if isinstance(values, str):
        stripped = values.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
            raw_values = parsed if isinstance(parsed, list) else stripped
        except Exception:
            raw_values = stripped
    if isinstance(raw_values, str):
        raw_values = raw_values.replace("，", ",").split(",")
    if not isinstance(raw_values, list):
        return []
    normalized = []
    for value in raw_values:
        text = str(value).strip()
        if text:
            normalized.append(text[:120])
    return list(dict.fromkeys(normalized))[:20]


def _shared_channel_normalize_tags(tags) -> list[str]:
    if tags is None:
        return []
    raw_tags = tags
    if isinstance(tags, str):
        stripped = tags.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
            raw_tags = parsed if isinstance(parsed, list) else stripped
        except Exception:
            raw_tags = stripped
    if isinstance(raw_tags, str):
        raw_tags = raw_tags.replace("，", ",").split(",")
    if not isinstance(raw_tags, list):
        return []
    normalized = []
    for tag in raw_tags:
        value = str(tag).strip()
        if not value:
            continue
        normalized.append(value[:40])
    return list(dict.fromkeys(normalized))[:12]


def _shared_channel_message_index(messages: list[dict], message_id: str) -> int:
    for idx, message in enumerate(messages):
        if message.get("id") == message_id:
            return idx
    return -1


def _shared_channel_visible_messages(store: dict, limit: int = 20, before: str = "") -> list[dict]:
    messages = [m for m in store.get("messages", []) if isinstance(m, dict)]
    if before:
        idx = _shared_channel_message_index(messages, before)
        if idx >= 0:
            messages = messages[:idx]
    limit = max(1, min(int(limit or 20), 100))
    return messages[-limit:]


def _shared_channel_unread_messages(store: dict, cursors: dict, reader: str) -> list[dict]:
    messages = [m for m in store.get("messages", []) if isinstance(m, dict)]
    cursor = str(cursors.get(reader, "") or "")
    start_idx = _shared_channel_message_index(messages, cursor) + 1 if cursor else 0
    return [m for m in messages[start_idx:] if m.get("sender") != reader]


def _shared_channel_status_payload() -> dict:
    store = _shared_channel_load_store()
    cursors = _shared_channel_load_cursors()
    messages = [m for m in store.get("messages", []) if isinstance(m, dict)]
    return {
        "status": "ok",
        "version": SHARED_CHANNEL_VERSION,
        "git_sha": _runtime_git_sha(),
        "write_scope": "shared_channel_only",
        "main_brain_write": False,
        "visibility": SHARED_CHANNEL_VISIBILITY,
        "canonical_base_url": SHARED_CHANNEL_CANONICAL_BASE_URL,
        "canonical_mcp_url": SHARED_ONLY_MCP_URL,
        "private_full_mcp_url": PRIVATE_FULL_MCP_URL,
        "canonical_status_url": f"{SHARED_CHANNEL_CANONICAL_BASE_URL}/shared/channel/status",
        "canonical_note": (
            "For the shared living-room wall, both Yechenyi and Guyanshen should connect "
            "their MCP clients to canonical_mcp_url, which exposes shared-room tools only. "
            "The private_full_mcp_url is Yechenyi private hippocampus access and should not be used by Guyanshen."
        ),
        "storage_dir": _shared_channel_dir(),
        "message_count": len(messages),
        "latest_message_id": messages[-1].get("id", "") if messages else "",
        "allowed_senders": list(SHARED_CHANNEL_ALLOWED_SENDERS),
        "readers": list(SHARED_CHANNEL_ALLOWED_SENDERS),
        "read_cursors": {sender: str(cursors.get(sender, "") or "") for sender in SHARED_CHANNEL_ALLOWED_SENDERS},
        "auth_token_supported": True,
        "auth_token_configured": bool(_shared_channel_auth_token()),
        "atomic_json_write": True,
        "endpoints": {
            "post": "/shared/channel/post",
            "read": "/shared/channel/read",
            "reply": "/shared/channel/reply",
            "unread": "/shared/channel/unread",
            "ack": "/shared/channel/ack",
            "status": "/shared/channel/status",
        },
        "mcp_tools": ["shared_post", "shared_read", "shared_reply", "shared_unread", "shared_ack", "shared_status"],
        "boundaries": [
            "Shared channel is for technical, engineering, deployment, upgrade, and ordinary collaboration notes.",
            "Do not share private intimate memory, account credentials, tokens, passwords, cookies, billing, or account identifiers.",
            "Messages do not automatically write to Yechenyi or Guyanshen main brain memory.",
        ],
    }


def _shared_space_status_payload() -> dict:
    store = _shared_space_load_store()
    items = [item for item in store.get("items", []) if isinstance(item, dict)]
    section_counts = {
        section: len([item for item in items if item.get("section") == section])
        for section in SHARED_SPACE_ALLOWED_SECTIONS
    }
    return {
        "status": "ok",
        "version": SHARED_SPACE_VERSION,
        "git_sha": _runtime_git_sha(),
        "write_scope": "shared_space_only",
        "main_brain_write": False,
        "canonical_base_url": SHARED_CHANNEL_CANONICAL_BASE_URL,
        "canonical_mcp_url": SHARED_ONLY_MCP_URL,
        "canonical_status_url": f"{SHARED_CHANNEL_CANONICAL_BASE_URL}/shared/space/status",
        "storage_dir": _shared_space_dir(),
        "item_count": len(items),
        "section_counts": section_counts,
        "sections": {
            "tech_shelf": "Shared technical references, tutorials, external post summaries, and reusable engineering lessons.",
            "house_rules": "Shared-space boundaries and operating rules visible to Qianqian, Yechenyi, and Guyanshen.",
            "shared_memory": "Common memories all three can know; not Yechenyi private memory and not Guyanshen private memory.",
            "todo": "Shared follow-ups for the living-room space, frontend, gateway, deployment, and coordination.",
        },
        "endpoints": {
            "status": "/shared/space/status",
            "add_item": "/shared/space/item",
            "list_items": "/shared/space/items",
            "add_tech_card": "/shared/space/tech-card",
        },
        "mcp_tools": ["shared_space_status", "shared_item_add", "shared_item_list", "shared_tech_card_add"],
        "boundaries": [
            "Shared space items do not automatically write to any private hippocampus.",
            "Do not store private intimate content, secrets, tokens, passwords, cookies, billing, or account identifiers.",
            "Promote an item into a private brain only by that brain's own explicit tool or review flow.",
        ],
    }


def _shared_travel_status_payload() -> dict:
    store = _shared_travel_load_store()
    souvenirs = [item for item in store.get("souvenirs", []) if isinstance(item, dict)]
    travelogues = [item for item in store.get("travelogues", []) if isinstance(item, dict)]
    by_traveler = {
        traveler: len([item for item in souvenirs if item.get("traveler") == traveler])
        for traveler in SHARED_CHANNEL_ALLOWED_SENDERS
    }
    by_traveler_counts = {
        traveler: {
            "souvenirs": len([item for item in souvenirs if item.get("traveler") == traveler]),
            "travelogues": len([item for item in travelogues if item.get("traveler") == traveler]),
        }
        for traveler in SHARED_CHANNEL_ALLOWED_SENDERS
    }
    return {
        "status": "ok",
        "version": SHARED_TRAVEL_VERSION,
        "git_sha": _runtime_git_sha(),
        "write_scope": "shared_travel_only",
        "main_brain_write": False,
        "room": SHARED_TRAVEL_ROOM_NAME,
        "canonical_base_url": SHARED_CHANNEL_CANONICAL_BASE_URL,
        "canonical_mcp_url": SHARED_ONLY_MCP_URL,
        "canonical_status_url": f"{SHARED_CHANNEL_CANONICAL_BASE_URL}/shared/travel/status",
        "storage_dir": _shared_travel_dir(),
        "souvenir_count": len(souvenirs),
        "travelogue_count": len(travelogues),
        "by_traveler": by_traveler,
        "by_traveler_counts": by_traveler_counts,
        "experience_modes": list(SHARED_TRAVEL_ALLOWED_MODES),
        "experience_policies": SHARED_TRAVEL_EXPERIENCE_POLICIES,
        "default_experience_policy_by_traveler": SHARED_TRAVEL_DEFAULT_POLICY_BY_TRAVELER,
        "endpoints": {
            "status": "/shared/travel/status",
            "add_souvenir": "/shared/travel/souvenir",
            "list_souvenirs": "/shared/travel/souvenirs",
            "add_travelogue": "/shared/travel/travelogue",
            "list_travelogues": "/shared/travel/travelogues",
            "atlas": "/shared/travel/atlas",
            "cabinet": "/shared/travel/cabinet",
        },
        "mcp_tools": [
            "shared_travel_status",
            "shared_souvenir_add",
            "shared_souvenir_list",
            "shared_travelogue_add",
            "shared_travelogue_list",
            "shared_travel_atlas",
            "shared_travel_cabinet",
        ],
        "boundaries": [
            "Travel entries are traceable experience records, not claims of physical AI travel.",
            "Generated travel can be emotionally immersive, but it must remain source-aware and reviewable.",
            "Yechenyi may use immersive_aftercare; Guyanshen defaults to transparent_preface unless he explicitly chooses otherwise.",
            "Use source_url/source_title when a souvenir comes from a public note, post, image, or user-provided text.",
            "Souvenirs can be displayed in the Moon Rose seaview living room frontend.",
            "Do not store secrets, account identifiers, private intimate content, or login-only material.",
        ],
    }


def _shared_room_sensory_manual_state(current: dict, now: datetime) -> dict:
    if not isinstance(current, dict):
        return {
            "mode": "empty",
            "is_initial_empty": True,
            "is_stale": True,
            "age_minutes": None,
            "stale_after_minutes": 60,
        }
    source = str(current.get("source") or "")
    updated_at = str(current.get("updated_at") or "")
    is_initial = source == "initial_empty_room" or not updated_at
    parsed = None
    if updated_at:
        try:
            parsed = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        except Exception:
            parsed = None
    age_minutes = None
    if parsed is not None:
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=CST)
        age_minutes = max(0, int((now - parsed.astimezone(CST)).total_seconds() // 60))
    stale_after = 60
    is_stale = is_initial or age_minutes is None or age_minutes >= stale_after
    return {
        "mode": "manual_override" if not is_initial else "initial_empty",
        "is_initial_empty": is_initial,
        "is_stale": is_stale,
        "age_minutes": age_minutes,
        "stale_after_minutes": stale_after,
    }


def _shared_room_auto_sensory_current(environment: dict) -> dict:
    environment = environment if isinstance(environment, dict) else {}
    now = environment.get("time_source", {}).get("now") or datetime.now(CST).isoformat()
    day_phase = environment.get("day_phase") if isinstance(environment.get("day_phase"), dict) else {}
    season = environment.get("season") if isinstance(environment.get("season"), dict) else {}
    weather = environment.get("weather") if isinstance(environment.get("weather"), dict) else {}
    weather_current = weather.get("current") if isinstance(weather.get("current"), dict) else {}
    atmosphere = environment.get("atmosphere") if isinstance(environment.get("atmosphere"), dict) else {}

    phase_label = day_phase.get("label") or "当前时段"
    weather_label = weather_current.get("weather_label") or ("杭州天气已连接" if weather.get("connected") else "杭州天气暂未连接")
    temperature = weather_current.get("temperature_c")
    temp_text = f"{temperature}°C" if temperature is not None else ""
    weather_text = "，".join(part for part in [weather_label, temp_text] if part)

    sight = " ".join(part for part in [
        atmosphere.get("sight", ""),
        f"客厅按{phase_label}自动换光；落地窗边的海玻璃会跟着天光变亮或变深。",
        f"大门外院子状态：{season.get('garden', '')}",
    ] if part).strip()
    sound = " ".join(part for part in [
        atmosphere.get("sound", ""),
        "如果前端打开体感层，可以把这段作为当前房间底噪，而不用人工重写。",
    ] if part).strip()
    felt = " ".join(part for part in [
        atmosphere.get("felt", ""),
        f"自动锚点：北京时间、{season.get('label', '季节')}、{phase_label}、{weather_text}。",
    ] if part).strip()

    return {
        "context": "room",
        "sight": sight[:500],
        "sound": sound[:500],
        "felt": felt[:500],
        "updated_by": "system_auto_environment",
        "updated_at": now,
        "source": "computed_from_shared_room_environment",
        "derived_from_environment": True,
        "version": SHARED_ROOM_SENSORY_AUTO_VERSION,
        "inputs": {
            "day_phase": day_phase.get("id", ""),
            "day_phase_label": phase_label,
            "season": season.get("id", ""),
            "season_label": season.get("label", ""),
            "weather_connected": bool(weather.get("connected")),
            "weather_label": weather_label,
            "temperature_c": temperature,
        },
    }


def _shared_room_sensory_status_payload(environment: dict = None) -> dict:
    store = _shared_room_sensory_load_store()
    now = datetime.now(CST)
    environment_payload = environment if isinstance(environment, dict) else _shared_room_environment_payload()
    manual_current = store.get("current", {})
    manual_state = _shared_room_sensory_manual_state(manual_current, now)
    auto_current = _shared_room_auto_sensory_current(environment_payload)
    effective_current = auto_current if manual_state.get("is_stale") else manual_current
    recent_souvenirs = _shared_souvenir_list(limit=6)
    return {
        "status": "ok",
        "version": SHARED_ROOM_SENSORY_VERSION,
        "auto_version": SHARED_ROOM_SENSORY_AUTO_VERSION,
        "git_sha": _runtime_git_sha(),
        "write_scope": "shared_room_sensory_only",
        "main_brain_write": False,
        "room": SHARED_TRAVEL_ROOM_NAME,
        "canonical_base_url": SHARED_CHANNEL_CANONICAL_BASE_URL,
        "canonical_mcp_url": SHARED_ONLY_MCP_URL,
        "canonical_status_url": f"{SHARED_CHANNEL_CANONICAL_BASE_URL}/shared/room/sensory/status",
        "storage_dir": _shared_room_dir(),
        "current": manual_current,
        "manual_current": manual_current,
        "manual_state": manual_state,
        "auto_current": auto_current,
        "effective_current": effective_current,
        "effective_source": "auto_current" if manual_state.get("is_stale") else "manual_current",
        "auto_update": {
            "enabled": True,
            "mode": "read_time_computed",
            "writes_json": False,
            "source_endpoint": "/shared/room/environment",
            "note": "Frontend and agents should prefer effective_current; manual sensory remains available as a temporary override.",
        },
        "history_count": len([item for item in store.get("history", []) if isinstance(item, dict)]),
        "visible_souvenirs": [
            {
                "id": item.get("id", ""),
                "title": item.get("title", ""),
                "place": item.get("place", ""),
                "traveler": item.get("traveler", ""),
                "experience_policy": _shared_travel_item_policy(item),
            }
            for item in recent_souvenirs
        ],
        "contexts": list(SHARED_ROOM_SENSORY_ALLOWED_CONTEXTS),
        "channels": ["sight", "sound", "felt"],
        "endpoints": {
            "status": "/shared/room/sensory/status",
            "update": "/shared/room/sensory",
            "environment_source": "/shared/room/environment",
        },
        "mcp_tools": ["shared_room_sensory_status", "shared_room_sensory_update"],
        "boundaries": [
            "Room sensory text is a generated/curated state layer, not a claim of physical embodiment.",
            "Write environmental stimuli and room details; avoid forcing conclusions like 'you feel happy'.",
            "The state is shared-room display data and does not write private hippocampus memory by itself.",
            "Do not store private intimate content, secrets, tokens, passwords, cookies, billing, or account identifiers.",
        ],
    }


async def _shared_room_sensory_update(
    updated_by: str,
    sight: str = "",
    sound: str = "",
    felt: str = "",
    context: str = "room",
    source: str = "",
) -> dict:
    updated_by = _shared_channel_normalize_sender(updated_by, "updated_by")
    context = _shared_room_sensory_normalize_context(context)
    sight = (sight or "").strip()[:500]
    sound = (sound or "").strip()[:500]
    felt = (felt or "").strip()[:500]
    if not any([sight, sound, felt]):
        raise ValueError("at least one sensory channel is required")
    source = (source or "").strip()[:80] or "unknown"
    async with _shared_room_sensory_lock:
        store = _shared_room_sensory_load_store()
        now = datetime.now(CST)
        previous = store.get("current", {}) if isinstance(store.get("current"), dict) else {}
        current = {
            "context": context,
            "sight": sight,
            "sound": sound,
            "felt": felt,
            "updated_by": updated_by,
            "updated_at": now.isoformat(),
            "source": source,
        }
        history = [item for item in store.get("history", []) if isinstance(item, dict)]
        if previous:
            history.append(previous)
        store["current"] = current
        store["history"] = history[-100:]
        store["updated_at"] = now.isoformat()
        _atomic_write_json(_shared_room_sensory_path(), store)
        return current


def _shared_pet_status_payload() -> dict:
    store = _shared_pet_load_store()
    pet = store.get("pet", {}) if isinstance(store.get("pet"), dict) else {}
    adopted = bool(store.get("adopted")) and bool(pet)
    needs = {}
    events = store.get("events") or []
    current_location = _shared_pet_normalize_location(str(store.get("current_location") or "window_seat"))
    collection_box = store.get("collection_box") or []
    if adopted:
        needs = {
            "hunger": _shared_pet_score(str(pet.get("last_fed_at") or pet.get("adopted_at") or ""), 8.0),
            "companionship": _shared_pet_score(str(pet.get("last_companion_at") or pet.get("adopted_at") or ""), 10.0),
            "play": _shared_pet_score(str(pet.get("last_played_at") or pet.get("adopted_at") or ""), 12.0),
            "cleanliness": _shared_pet_score(str(pet.get("last_cleaned_at") or pet.get("adopted_at") or ""), 24.0),
        }
    return {
        "status": "ok",
        "version": SHARED_PET_VERSION,
        "git_sha": _runtime_git_sha(),
        "write_scope": "shared_pet_only",
        "main_brain_write": False,
        "room": SHARED_TRAVEL_ROOM_NAME,
        "adopted": adopted,
        "pet": pet if adopted else {},
        "adoption_card": _shared_pet_adoption_card(pet) if adopted else {},
        "care_principles": SHARED_PET_CARE_PRINCIPLES,
        "current_location": {
            "id": current_location,
            "label": _shared_pet_location_label(current_location),
        },
        "today_care": _shared_pet_today_care(events),
        "collection_box": collection_box[-50:],
        "needs": needs,
        "events": events[-20:],
        "allowed_actions": list(SHARED_PET_ALLOWED_ACTIONS),
        "allowed_locations": list(SHARED_PET_ALLOWED_LOCATIONS),
        "endpoints": {
            "status": "/shared/pet/status",
            "adopt": "/shared/pet/adopt",
            "interact": "/shared/pet/interact",
            "collect": "/shared/pet/collect",
        },
        "mcp_tools": ["shared_pet_status", "shared_pet_adopt", "shared_pet_interact", "shared_pet_collect"],
        "adoption_note": "No pet is adopted until Qianqian, Yechenyi, and Guyanshen agree on species/name.",
        "boundaries": [
            "The shared pet is a simulated living-room companion, not a real animal or a private memory write.",
            "Needs can decay as display state, but the pet must not guilt-trip or pressure Qianqian.",
            "No proactive notifications or real-world actions are enabled by this pet state alone.",
        ],
    }


async def _shared_pet_adopt(
    name: str,
    species: str,
    adopted_by: str,
    traits: str = "",
    origin_note: str = "",
    appearance: str = "",
    personality: str = "",
    habits: str = "",
    care_boundaries: str = "",
    one_sentence: str = "",
    agreement_note: str = "",
    source: str = "",
) -> dict:
    name = _shared_space_normalize_title(name)
    species = _shared_space_normalize_title(species)
    adopted_by = _shared_channel_normalize_sender(adopted_by, "adopted_by")
    traits_list = _shared_channel_normalize_tags(traits)
    profile = {
        "origin_note": _shared_pet_normalize_profile_text(origin_note),
        "appearance": _shared_pet_normalize_profile_text(appearance),
        "personality": _shared_pet_normalize_profile_text(personality),
        "habits": _shared_pet_normalize_profile_text(habits),
        "care_boundaries": _shared_pet_normalize_profile_text(care_boundaries),
        "one_sentence": _shared_pet_normalize_profile_text(one_sentence, 500),
    }
    if name == "小Y" and species == "月鸮狐":
        for key, default_value in SHARED_PET_XIAOY_DEFAULT_PROFILE.items():
            if not profile.get(key):
                limit = 500 if key == "one_sentence" else SHARED_PET_MAX_PROFILE_CHARS
                profile[key] = _shared_pet_normalize_profile_text(default_value, limit)
    agreement_note = (agreement_note or "").strip()[:500]
    source = (source or "").strip()[:80] or "unknown"
    async with _shared_pet_lock:
        store = _shared_pet_load_store()
        if store.get("adopted") and store.get("pet"):
            raise ValueError("shared pet already adopted")
        now = datetime.now(CST)
        pet = {
            "name": name,
            "species": species,
            "traits": traits_list,
            "profile": profile,
            "adopted_by": adopted_by,
            "agreement_note": agreement_note,
            "adopted_at": now.isoformat(),
            "last_fed_at": now.isoformat(),
            "last_played_at": now.isoformat(),
            "last_companion_at": now.isoformat(),
            "last_cleaned_at": now.isoformat(),
            "source": source,
        }
        event = {
            "type": "adopt",
            "actor": adopted_by,
            "note": agreement_note,
            "one_sentence": profile.get("one_sentence", ""),
            "created_at": now.isoformat(),
            "source": source,
        }
        store["adopted"] = True
        store["pet"] = pet
        store["current_location"] = "window_seat"
        store.setdefault("collection_box", [])
        store["events"] = (store.get("events") or [])[-99:] + [event]
        store["updated_at"] = now.isoformat()
        _atomic_write_json(_shared_pet_path(), store)
        return pet


async def _shared_pet_interact(
    action: str,
    actor: str,
    note: str = "",
    location: str = "",
    source: str = "",
) -> dict:
    action = _shared_pet_normalize_action(action)
    actor = _shared_channel_normalize_sender(actor, "actor")
    note = (note or "").strip()[:500]
    normalized_location = _shared_pet_normalize_location(location or _shared_pet_infer_location(action))
    source = (source or "").strip()[:80] or "unknown"
    async with _shared_pet_lock:
        store = _shared_pet_load_store()
        if not store.get("adopted") or not store.get("pet"):
            raise ValueError("no shared pet adopted yet")
        now = datetime.now(CST)
        pet = store["pet"]
        if action == "feed":
            pet["last_fed_at"] = now.isoformat()
        elif action == "play":
            pet["last_played_at"] = now.isoformat()
            pet["last_companion_at"] = now.isoformat()
        elif action == "pet":
            pet["last_companion_at"] = now.isoformat()
        elif action == "clean":
            pet["last_cleaned_at"] = now.isoformat()
        elif action == "checkin":
            pet["last_companion_at"] = now.isoformat()
        store["current_location"] = normalized_location
        event = {
            "type": "interact",
            "action": action,
            "actor": actor,
            "note": note,
            "location": normalized_location,
            "created_at": now.isoformat(),
            "source": source,
        }
        store["pet"] = pet
        store["events"] = (store.get("events") or [])[-99:] + [event]
        store["updated_at"] = now.isoformat()
        _atomic_write_json(_shared_pet_path(), store)
        return event


async def _shared_pet_collect(
    item_name: str,
    found_by: str,
    source_place: str = "",
    story: str = "",
    source: str = "",
) -> dict:
    item_name = _shared_space_normalize_title(item_name)
    found_by = _shared_channel_normalize_sender(found_by, "found_by")
    source_place = (source_place or "").strip()[:120]
    story = (story or "").strip()[:1000]
    source = (source or "").strip()[:80] or "unknown"
    async with _shared_pet_lock:
        store = _shared_pet_load_store()
        if not store.get("adopted") or not store.get("pet"):
            raise ValueError("no shared pet adopted yet")
        now = datetime.now(CST)
        item = {
            "id": f"pet_item_{now.strftime('%Y%m%d_%H%M%S_%f')}",
            "item_name": item_name,
            "found_by": found_by,
            "source_place": source_place,
            "story": story,
            "created_at": now.isoformat(),
            "source": source,
        }
        event = {
            "type": "collect",
            "actor": found_by,
            "item_name": item_name,
            "source_place": source_place,
            "story": story,
            "created_at": now.isoformat(),
            "source": source,
        }
        store["collection_box"] = (store.get("collection_box") or [])[-99:] + [item]
        store["events"] = (store.get("events") or [])[-99:] + [event]
        store["updated_at"] = now.isoformat()
        _atomic_write_json(_shared_pet_path(), store)
        return item


async def _shared_space_add_item(
    section: str,
    title: str,
    content: str,
    sender: str,
    tags=None,
    source: str = "",
    extra_fields: dict | None = None,
) -> dict:
    section = _shared_space_normalize_section(section)
    sender = _shared_channel_normalize_sender(sender)
    title = _shared_space_normalize_title(title)
    content = _shared_space_normalize_content(content)
    tag_list = _shared_channel_normalize_tags(tags)
    source = (source or "").strip()[:80] or "unknown"

    async with _shared_space_lock:
        store = _shared_space_load_store()
        now = datetime.now(CST)
        item = {
            "id": f"item_{now.strftime('%Y%m%d_%H%M%S_%f')}_{random.randint(1000, 9999)}",
            "section": section,
            "title": title,
            "content": content,
            "sender": sender,
            "tags": tag_list,
            "created_at": now.isoformat(),
            "visibility": "shared_room",
            "source": source,
        }
        if extra_fields:
            item.update(extra_fields)
        store["items"].append(item)
        store["updated_at"] = now.isoformat()
        _atomic_write_json(_shared_space_items_path(), store)
        return item


async def _shared_tech_card_add(
    title: str,
    summary: str,
    sender: str,
    url: str = "",
    source_author: str = "",
    status: str = "unverified",
    verified_by: str = "",
    tags=None,
    source: str = "",
) -> dict:
    status = _shared_tech_card_normalize_status(status)
    verified_by = (verified_by or "").strip().lower()
    if verified_by:
        verified_by = _shared_channel_normalize_sender(verified_by, "verified_by")
    normalized_tags = _shared_channel_normalize_tags(tags)
    normalized_tags = list(dict.fromkeys(normalized_tags + ["tech_card", status]))
    extra_fields = {
        "card_type": "tech_reference",
        "url": _shared_tech_card_normalize_url(url),
        "source_author": (source_author or "").strip()[:120],
        "summary": _shared_space_normalize_content(summary),
        "status": status,
        "verified_by": verified_by,
    }
    return await _shared_space_add_item(
        "tech_shelf",
        title,
        summary,
        sender,
        tags=normalized_tags,
        source=source or "tech_card",
        extra_fields=extra_fields,
    )


async def _shared_souvenir_add(
    title: str,
    place: str,
    story: str,
    traveler: str,
    sensory=None,
    source_url: str = "",
    source_title: str = "",
    experience_mode: str = "remote_source",
    experience_policy: str = "",
    tags=None,
    source: str = "",
) -> dict:
    title = _shared_space_normalize_title(title)
    place = _shared_space_normalize_title(place)
    story = _shared_space_normalize_content(story)
    traveler = _shared_channel_normalize_sender(traveler, "traveler")
    experience_mode = _shared_travel_normalize_mode(experience_mode)
    experience_policy = _shared_travel_normalize_policy(experience_policy, traveler)
    tag_list = list(dict.fromkeys(_shared_channel_normalize_tags(tags) + ["travel_souvenir", experience_mode, experience_policy]))
    sensory_data = _shared_travel_normalize_sensory(sensory)
    source = (source or "").strip()[:80] or "unknown"

    async with _shared_travel_lock:
        store = _shared_travel_load_store()
        now = datetime.now(CST)
        souvenir = {
            "id": f"souvenir_{now.strftime('%Y%m%d_%H%M%S_%f')}_{random.randint(1000, 9999)}",
            "title": title,
            "place": place,
            "story": story,
            "traveler": traveler,
            "sensory": sensory_data,
            "source_url": _shared_tech_card_normalize_url(source_url),
            "source_title": (source_title or "").strip()[:160],
            "experience_mode": experience_mode,
            "experience_policy": experience_policy,
            "tags": tag_list,
            "created_at": now.isoformat(),
            "display_room": SHARED_TRAVEL_ROOM_NAME,
            "visibility": "shared_travel",
            "source": source,
        }
        store["souvenirs"].append(souvenir)
        store["updated_at"] = now.isoformat()
        _atomic_write_json(_shared_travel_souvenirs_path(), store)
        return souvenir


def _shared_souvenir_list(limit: int = 20, traveler: str = "", tag: str = "") -> list[dict]:
    store = _shared_travel_load_store()
    souvenirs = [item for item in store.get("souvenirs", []) if isinstance(item, dict)]
    if traveler:
        traveler = _shared_channel_normalize_sender(traveler, "traveler")
        souvenirs = [item for item in souvenirs if item.get("traveler") == traveler]
    if tag:
        normalized_tag = tag.strip()
        souvenirs = [item for item in souvenirs if normalized_tag in (item.get("tags") or [])]
    limit = max(1, min(int(limit or 20), 100))
    return souvenirs[-limit:]


async def _shared_travelogue_add(
    title: str,
    place: str,
    narrative: str,
    traveler: str,
    scenes=None,
    souvenir_ids=None,
    source_url: str = "",
    source_title: str = "",
    experience_mode: str = "remote_source",
    experience_policy: str = "",
    tags=None,
    source: str = "",
) -> dict:
    title = _shared_space_normalize_title(title)
    place = _shared_space_normalize_title(place)
    narrative = _shared_space_normalize_content(narrative)
    traveler = _shared_channel_normalize_sender(traveler, "traveler")
    experience_mode = _shared_travel_normalize_mode(experience_mode)
    experience_policy = _shared_travel_normalize_policy(experience_policy, traveler)
    scene_list = _shared_travel_normalize_scene_list(scenes)
    souvenir_id_list = _shared_travel_normalize_id_list(souvenir_ids)
    tag_list = list(dict.fromkeys(_shared_channel_normalize_tags(tags) + ["travelogue", experience_mode, experience_policy]))
    source = (source or "").strip()[:80] or "unknown"

    async with _shared_travel_lock:
        store = _shared_travel_load_store()
        now = datetime.now(CST)
        travelogue = {
            "id": f"travelogue_{now.strftime('%Y%m%d_%H%M%S_%f')}_{random.randint(1000, 9999)}",
            "title": title,
            "place": place,
            "narrative": narrative,
            "traveler": traveler,
            "scenes": scene_list,
            "souvenir_ids": souvenir_id_list,
            "source_url": _shared_tech_card_normalize_url(source_url),
            "source_title": (source_title or "").strip()[:160],
            "experience_mode": experience_mode,
            "experience_policy": experience_policy,
            "tags": tag_list,
            "created_at": now.isoformat(),
            "display_room": SHARED_TRAVEL_ROOM_NAME,
            "visibility": "shared_travel",
            "source": source,
        }
        store["travelogues"].append(travelogue)
        store["updated_at"] = now.isoformat()
        _atomic_write_json(_shared_travel_souvenirs_path(), store)
        return travelogue


def _shared_travelogue_list(limit: int = 20, traveler: str = "", tag: str = "") -> list[dict]:
    store = _shared_travel_load_store()
    travelogues = [item for item in store.get("travelogues", []) if isinstance(item, dict)]
    if traveler:
        traveler = _shared_channel_normalize_sender(traveler, "traveler")
        travelogues = [item for item in travelogues if item.get("traveler") == traveler]
    if tag:
        normalized_tag = tag.strip()
        travelogues = [item for item in travelogues if normalized_tag in (item.get("tags") or [])]
    limit = max(1, min(int(limit or 20), 100))
    return travelogues[-limit:]


def _shared_travel_atlas_payload(limit: int = 50, traveler: str = "", tag: str = "") -> dict:
    store = _shared_travel_load_store()
    souvenirs = [item for item in store.get("souvenirs", []) if isinstance(item, dict)]
    travelogues = [item for item in store.get("travelogues", []) if isinstance(item, dict)]
    if traveler:
        traveler = _shared_channel_normalize_sender(traveler, "traveler")
        souvenirs = [item for item in souvenirs if item.get("traveler") == traveler]
        travelogues = [item for item in travelogues if item.get("traveler") == traveler]
    if tag:
        normalized_tag = tag.strip()
        souvenirs = [item for item in souvenirs if normalized_tag in (item.get("tags") or [])]
        travelogues = [item for item in travelogues if normalized_tag in (item.get("tags") or [])]

    places: dict[str, dict] = {}

    def place_entry(place: str) -> dict:
        normalized_place = (place or "未命名地点").strip()[:160] or "未命名地点"
        if normalized_place not in places:
            places[normalized_place] = {
                "place": normalized_place,
                "souvenir_count": 0,
                "travelogue_count": 0,
                "souvenir_ids": [],
                "travelogue_ids": [],
                "travelers": set(),
                "tags": set(),
                "experience_modes": set(),
                "experience_policies": set(),
                "latest_at": "",
            }
        return places[normalized_place]

    def add_common(entry: dict, item: dict) -> None:
        traveler_value = str(item.get("traveler") or "").strip()
        if traveler_value:
            entry["travelers"].add(traveler_value)
        for value in item.get("tags") or []:
            if value:
                entry["tags"].add(str(value))
        mode = str(item.get("experience_mode") or "").strip()
        if mode:
            entry["experience_modes"].add(mode)
        entry["experience_policies"].add(_shared_travel_item_policy(item))
        created_at = str(item.get("created_at") or "")
        if created_at > entry["latest_at"]:
            entry["latest_at"] = created_at

    for souvenir in souvenirs:
        entry = place_entry(str(souvenir.get("place") or ""))
        entry["souvenir_count"] += 1
        souvenir_id = str(souvenir.get("id") or "")
        if souvenir_id:
            entry["souvenir_ids"].append(souvenir_id)
        add_common(entry, souvenir)

    for travelogue in travelogues:
        entry = place_entry(str(travelogue.get("place") or ""))
        entry["travelogue_count"] += 1
        travelogue_id = str(travelogue.get("id") or "")
        if travelogue_id:
            entry["travelogue_ids"].append(travelogue_id)
        add_common(entry, travelogue)

    limit = max(1, min(int(limit or 50), 100))
    normalized_places = []
    for entry in places.values():
        normalized_places.append({
            **entry,
            "souvenir_ids": entry["souvenir_ids"][-20:],
            "travelogue_ids": entry["travelogue_ids"][-20:],
            "travelers": sorted(entry["travelers"]),
            "tags": sorted(entry["tags"])[:20],
            "experience_modes": sorted(entry["experience_modes"]),
            "experience_policies": sorted(entry["experience_policies"]),
        })
    normalized_places.sort(key=lambda item: item.get("latest_at", ""), reverse=True)
    return {
        "status": "ok",
        "version": "shared_travel_atlas_v1",
        "git_sha": _runtime_git_sha(),
        "write_scope": "read_only",
        "main_brain_write": False,
        "room": SHARED_TRAVEL_ROOM_NAME,
        "place_count": len(normalized_places),
        "places": normalized_places[:limit],
        "filters": {"traveler": traveler, "tag": tag},
        "endpoints": {"atlas": "/shared/travel/atlas"},
        "mcp_tools": ["shared_travel_atlas"],
        "boundaries": [
            "Atlas places summarize traceable generated/remote/user-story experiences.",
            "Atlas entries do not claim physical travel or private memory promotion.",
        ],
    }


def _shared_room_display_payload(limit: int = 50) -> dict:
    limit = max(1, min(int(limit or 50), 100))
    store = _shared_travel_load_store()
    display_store = _shared_room_display_load_store()
    placements = display_store.get("placements", {}) if isinstance(display_store.get("placements"), dict) else {}
    souvenirs = [item for item in store.get("souvenirs", []) if isinstance(item, dict)][-limit:]
    travelogues = [item for item in store.get("travelogues", []) if isinstance(item, dict)][-limit:]
    travelogue_by_souvenir: dict[str, list[str]] = {}
    for travelogue in travelogues:
        travelogue_id = str(travelogue.get("id") or "")
        if not travelogue_id:
            continue
        for souvenir_id in travelogue.get("souvenir_ids") or []:
            sid = str(souvenir_id)
            travelogue_by_souvenir.setdefault(sid, []).append(travelogue_id)

    zones = {
        zone: {
            "zone": zone,
            "label": spec.get("label", zone),
            "objects": [],
        }
        for zone, spec in SHARED_ROOM_DISPLAY_ZONES.items()
    }
    for souvenir in souvenirs:
        place = str(souvenir.get("place") or "")
        souvenir_id = str(souvenir.get("id") or "")
        placement = placements.get(souvenir_id, {}) if souvenir_id else {}
        zone = placement.get("zone") if isinstance(placement, dict) else ""
        if zone not in SHARED_ROOM_DISPLAY_ZONES:
            zone = _shared_room_display_zone_for_place(place)
        zones[zone]["objects"].append({
            "id": souvenir_id,
            "type": "souvenir",
            "title": souvenir.get("title", ""),
            "place": place,
            "traveler": souvenir.get("traveler", ""),
            "sensory": souvenir.get("sensory", {}),
            "experience_mode": souvenir.get("experience_mode", ""),
            "experience_policy": _shared_travel_item_policy(souvenir),
            "travelogue_ids": travelogue_by_souvenir.get(souvenir_id, []),
            "placement": placement if isinstance(placement, dict) else {},
            "created_at": souvenir.get("created_at", ""),
        })

    normalized_zones = []
    for zone in SHARED_ROOM_DISPLAY_ZONES:
        entry = zones[zone]
        entry["object_count"] = len(entry["objects"])
        normalized_zones.append(entry)
    current_sensory = _shared_room_sensory_load_store().get("current", {})
    return {
        "status": "ok",
        "version": "shared_room_display_v1",
        "git_sha": _runtime_git_sha(),
        "write_scope": "read_only",
        "main_brain_write": False,
        "room": SHARED_TRAVEL_ROOM_NAME,
        "display_name": "月光玫瑰海景房客厅",
        "zones": normalized_zones,
        "placement_count": len(placements),
        "current_sensory": current_sensory if isinstance(current_sensory, dict) else {},
        "endpoints": {
            "display": "/shared/room/display",
            "place_object": "/shared/room/place",
        },
        "mcp_tools": ["shared_room_display", "shared_room_place_object"],
        "boundaries": [
            "Room display is frontend layout data derived from shared travel objects.",
            "Display entries do not write or promote private hippocampus memory.",
        ],
    }


def _shared_travel_cabinet_payload(limit: int = 50, traveler: str = "") -> dict:
    limit = max(1, min(int(limit or 50), 100))
    if traveler:
        traveler = _shared_channel_normalize_sender(traveler, "traveler")
    store = _shared_travel_load_store()
    display_store = _shared_room_display_load_store()
    placements = display_store.get("placements", {}) if isinstance(display_store.get("placements"), dict) else {}
    souvenirs = [item for item in store.get("souvenirs", []) if isinstance(item, dict)]
    travelogues = [item for item in store.get("travelogues", []) if isinstance(item, dict)]
    if traveler:
        souvenirs = [item for item in souvenirs if item.get("traveler") == traveler]
        travelogues = [item for item in travelogues if item.get("traveler") == traveler]

    travelogue_by_souvenir: dict[str, list[dict]] = {}
    for travelogue in travelogues:
        summary = {
            "id": travelogue.get("id", ""),
            "title": travelogue.get("title", ""),
            "place": travelogue.get("place", ""),
            "created_at": travelogue.get("created_at", ""),
        }
        for souvenir_id in travelogue.get("souvenir_ids") or []:
            sid = str(souvenir_id)
            travelogue_by_souvenir.setdefault(sid, []).append(summary)

    shelves = {
        sender: {
            "traveler": sender,
            "label": {
                "yechenyi": "叶辰一的旅行格",
                "guyanshen": "顾砚深的旅行格",
                "system": "共享/系统格",
            }.get(sender, sender),
            "objects": [],
            "travelogues": [],
            "places": set(),
        }
        for sender in SHARED_CHANNEL_ALLOWED_SENDERS
        if not traveler or sender == traveler
    }

    for souvenir in souvenirs[-limit:]:
        shelf = shelves.get(str(souvenir.get("traveler") or "system"))
        if not shelf:
            continue
        souvenir_id = str(souvenir.get("id") or "")
        placement = placements.get(souvenir_id, {}) if souvenir_id else {}
        zone = placement.get("zone") if isinstance(placement, dict) else ""
        if zone not in SHARED_ROOM_DISPLAY_ZONES:
            zone = _shared_room_display_zone_for_place(str(souvenir.get("place") or ""))
        place = str(souvenir.get("place") or "")
        if place:
            shelf["places"].add(place)
        shelf["objects"].append({
            "id": souvenir_id,
            "title": souvenir.get("title", ""),
            "place": place,
            "display_zone": zone,
            "display_zone_label": SHARED_ROOM_DISPLAY_ZONES[zone].get("label", zone),
            "sensory": souvenir.get("sensory", {}),
            "experience_mode": souvenir.get("experience_mode", ""),
            "experience_policy": _shared_travel_item_policy(souvenir),
            "travelogues": travelogue_by_souvenir.get(souvenir_id, []),
            "created_at": souvenir.get("created_at", ""),
        })

    for travelogue in travelogues[-limit:]:
        shelf = shelves.get(str(travelogue.get("traveler") or "system"))
        if not shelf:
            continue
        place = str(travelogue.get("place") or "")
        if place:
            shelf["places"].add(place)
        shelf["travelogues"].append({
            "id": travelogue.get("id", ""),
            "title": travelogue.get("title", ""),
            "place": place,
            "souvenir_ids": travelogue.get("souvenir_ids", []),
            "experience_mode": travelogue.get("experience_mode", ""),
            "experience_policy": _shared_travel_item_policy(travelogue),
            "created_at": travelogue.get("created_at", ""),
        })

    normalized_shelves = []
    for shelf in shelves.values():
        normalized_shelves.append({
            "traveler": shelf["traveler"],
            "label": shelf["label"],
            "object_count": len(shelf["objects"]),
            "travelogue_count": len(shelf["travelogues"]),
            "place_count": len(shelf["places"]),
            "places": sorted(shelf["places"])[:20],
            "objects": shelf["objects"],
            "travelogues": shelf["travelogues"],
        })
    return {
        "status": "ok",
        "version": "shared_travel_cabinet_v1",
        "git_sha": _runtime_git_sha(),
        "write_scope": "read_only",
        "main_brain_write": False,
        "room": SHARED_TRAVEL_ROOM_NAME,
        "display_name": "旅行陈列柜",
        "shelves": normalized_shelves,
        "filters": {"traveler": traveler},
        "endpoints": {"cabinet": "/shared/travel/cabinet"},
        "mcp_tools": ["shared_travel_cabinet"],
        "boundaries": [
            "The cabinet displays shared travel records and souvenirs; it does not claim physical travel.",
            "Cabinet entries do not write or promote private hippocampus memory.",
        ],
    }


async def _shared_room_place_object(
    object_id: str,
    zone: str,
    placed_by: str,
    note: str = "",
    source: str = "",
) -> dict:
    object_id = (object_id or "").strip()
    if not object_id:
        raise ValueError("object_id is required")
    zone = _shared_room_display_normalize_zone(zone)
    placed_by = _shared_channel_normalize_sender(placed_by, "placed_by")
    note = (note or "").strip()[:300]
    source = (source or "").strip()[:80] or "unknown"
    store = _shared_travel_load_store()
    souvenirs = [item for item in store.get("souvenirs", []) if isinstance(item, dict)]
    if not any(str(item.get("id") or "") == object_id for item in souvenirs):
        raise ValueError("object_id does not match a known shared travel souvenir")

    async with _shared_room_display_lock:
        display_store = _shared_room_display_load_store()
        now = datetime.now(CST)
        placement = {
            "object_id": object_id,
            "zone": zone,
            "zone_label": SHARED_ROOM_DISPLAY_ZONES[zone].get("label", zone),
            "placed_by": placed_by,
            "note": note,
            "updated_at": now.isoformat(),
            "source": source,
        }
        display_store["placements"][object_id] = placement
        display_store["updated_at"] = now.isoformat()
        _atomic_write_json(_shared_room_display_path(), display_store)
        return placement


def _shared_space_list_items(section: str = "", limit: int = 20, tag: str = "") -> list[dict]:
    store = _shared_space_load_store()
    items = [item for item in store.get("items", []) if isinstance(item, dict)]
    if section:
        section = _shared_space_normalize_section(section)
        items = [item for item in items if item.get("section") == section]
    if tag:
        normalized_tag = tag.strip()
        items = [item for item in items if normalized_tag in (item.get("tags") or [])]
    limit = max(1, min(int(limit or 20), 100))
    return items[-limit:]


def _shared_room_environment_season(month: int) -> dict:
    if month in (3, 4, 5):
        return {
            "id": "spring",
            "label": "春",
            "garden": "院子里樱花和新叶最亮，茶花接近尾声，爬藤月季开始抽枝。",
            "plants": {
                "camellia": "早春余花或花后新叶",
                "cherry_blossom": "盛开到落英之间",
                "climbing_rose_wall": "新枝攀墙，花苞开始准备",
            },
        }
    if month in (6, 7, 8):
        return {
            "id": "summer",
            "label": "夏",
            "garden": "爬藤月季墙最繁盛，院子绿意很深，海风里有温热潮气。",
            "plants": {
                "camellia": "浓绿叶片为主",
                "cherry_blossom": "樱树成荫",
                "climbing_rose_wall": "花墙繁茂",
            },
        }
    if month in (9, 10, 11):
        return {
            "id": "autumn",
            "label": "秋",
            "garden": "花少一些，藤叶和樱树叶开始转色，院子变得安静清透。",
            "plants": {
                "camellia": "准备冬春花期",
                "cherry_blossom": "叶色转暖",
                "climbing_rose_wall": "花后修整，藤叶渐深",
            },
        }
    return {
        "id": "winter",
        "label": "冬",
        "garden": "枝条清冷，茶花撑起冬季花色，海边空气更干净。",
        "plants": {
            "camellia": "冬季花色主角",
            "cherry_blossom": "枝条休眠",
            "climbing_rose_wall": "藤架安静，等春天再醒",
        },
    }


def _shared_room_environment_day_phase(hour: int) -> dict:
    if 5 <= hour <= 6:
        return {
            "id": "dawn",
            "label": "清晨",
            "light": "海面发蓝，落地窗边有一点冷金色。",
            "sea": "悬崖下的海刚亮起来，浪声比人声先醒。",
        }
    if 7 <= hour <= 10:
        return {
            "id": "morning",
            "label": "上午",
            "light": "日光从落地窗铺进客厅，玻璃边缘很亮。",
            "sea": "海面清澈，适合把纪念品拿到窗边看。",
        }
    if 11 <= hour <= 14:
        return {
            "id": "noon",
            "label": "正午",
            "light": "房间光线稳定，院子和海面都很清楚。",
            "sea": "海色偏亮，悬崖边风声干净。",
        }
    if 15 <= hour <= 17:
        return {
            "id": "afternoon",
            "label": "午后",
            "light": "光线斜下来，客厅影子变长。",
            "sea": "海面开始有柔和反光，像慢慢收拢的一天。",
        }
    if 18 <= hour <= 19:
        return {
            "id": "dusk",
            "label": "黄昏",
            "light": "落地窗外有橙金色，日落把海面照暖。",
            "sea": "悬崖海边进入日落时段，适合看远方。",
        }
    if 20 <= hour <= 22:
        return {
            "id": "evening",
            "label": "夜晚",
            "light": "客厅灯亮起来，窗外海面退成深蓝。",
            "sea": "只能看见暗色海线和一点月光。",
        }
    return {
        "id": "late_night",
        "label": "深夜",
        "light": "房间安静，落地窗像一块深色镜面。",
        "sea": "浪声留在远处，院子和海边都睡着了。",
    }


def _shared_room_weather_code_label(code) -> str:
    try:
        code = int(code)
    except Exception:
        return "未知"
    labels = {
        0: "晴",
        1: "大部晴朗",
        2: "局部多云",
        3: "阴",
        45: "雾",
        48: "霜雾",
        51: "小毛毛雨",
        53: "毛毛雨",
        55: "较强毛毛雨",
        61: "小雨",
        63: "中雨",
        65: "大雨",
        71: "小雪",
        73: "中雪",
        75: "大雪",
        80: "阵雨",
        81: "较强阵雨",
        82: "强阵雨",
        95: "雷雨",
        96: "雷雨伴冰雹",
        99: "强雷雨伴冰雹",
    }
    return labels.get(code, f"天气代码 {code}")


def _shared_room_hangzhou_weather() -> dict:
    weather = {
        "connected": False,
        "provider": "open-meteo",
        "location": {
            "id": "hangzhou",
            "name": "杭州",
            "latitude": 30.2741,
            "longitude": 120.1551,
            "timezone": "Asia/Shanghai",
            "privacy_note": "Fixed public city weather; no device location, account, token, or IP lookup is used by this app.",
        },
        "current": {},
        "error": "",
    }
    if os.environ.get("OMBRE_ROOM_WEATHER_ENABLED", "true").lower() in ("0", "false", "no"):
        weather["error"] = "disabled_by_env"
        return weather

    try:
        response = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": weather["location"]["latitude"],
                "longitude": weather["location"]["longitude"],
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
                "timezone": "Asia/Shanghai",
            },
            timeout=2.5,
        )
        response.raise_for_status()
        data = response.json()
        current = data.get("current") if isinstance(data, dict) else {}
        if not isinstance(current, dict):
            raise ValueError("missing current weather")
        weather["connected"] = True
        weather["current"] = {
            "time": current.get("time", ""),
            "temperature_c": current.get("temperature_2m"),
            "apparent_temperature_c": current.get("apparent_temperature"),
            "relative_humidity_percent": current.get("relative_humidity_2m"),
            "precipitation_mm": current.get("precipitation"),
            "wind_speed_kmh": current.get("wind_speed_10m"),
            "weather_code": current.get("weather_code"),
            "weather_label": _shared_room_weather_code_label(current.get("weather_code")),
        }
    except Exception as e:
        weather["error"] = str(e)[:200]
    return weather


def _shared_room_weather_atmosphere(weather: dict) -> dict:
    if not weather.get("connected"):
        return {
            "sight": "",
            "sound": "远处有海浪声；杭州天气暂时拿不到时，房间仍按真实时间和季节运行。",
            "felt": "",
        }
    current = weather.get("current") if isinstance(weather.get("current"), dict) else {}
    label = current.get("weather_label") or "天气"
    temp = current.get("temperature_c")
    wind = current.get("wind_speed_kmh")
    precipitation = current.get("precipitation_mm")
    sight = f"杭州当前天气：{label}"
    if temp is not None:
        sight += f"，{temp}°C"
    if precipitation not in (None, 0, 0.0):
        sight += f"，降水 {precipitation}mm"
    sound = "远处有海浪声。"
    if precipitation not in (None, 0, 0.0):
        sound += "杭州有雨，窗边可以带一点雨天玻璃感。"
    felt = "房间天光跟随北京时间，天气锚点取杭州。"
    if wind is not None:
        felt += f" 风速约 {wind}km/h。"
    return {"sight": sight, "sound": sound, "felt": felt}


def _shared_room_environment_payload() -> dict:
    now = datetime.now(CST)
    season = _shared_room_environment_season(now.month)
    day_phase = _shared_room_environment_day_phase(now.hour)
    weather = _shared_room_hangzhou_weather()
    weather_atmosphere = _shared_room_weather_atmosphere(weather)
    return {
        "status": "ok",
        "version": SHARED_ROOM_ENVIRONMENT_VERSION,
        "git_sha": _runtime_git_sha(),
        "write_scope": "read_only",
        "main_brain_write": False,
        "room": SHARED_TRAVEL_ROOM_NAME,
        "display_name": "月光玫瑰海景房",
        "time_source": {
            "timezone": "Asia/Shanghai",
            "now": now.isoformat(),
            "derived_from_real_time": True,
            "weather_connected": bool(weather.get("connected")),
        },
        "weather": weather,
        "future_location_policy": {
            "user_authorized_location_supported_later": True,
            "current_mode": "fixed_city_hangzhou",
            "notes": [
                "A future Gaode/Amap layer can use Qianqian-authorized location states such as home, office, or on-the-way.",
                "That layer should be explicit, switchable, auditable, and should avoid storing raw tracks by default.",
            ],
        },
        "day_phase": day_phase,
        "season": season,
        "layout": {
            "floor_to_ceiling_window": {
                "label": "落地窗",
                "faces": "cliff_sea",
                "view": day_phase["sea"],
                "role": "看远方、日出日落、海面、旅行纪念品展示",
            },
            "front_door": {
                "label": "大门",
                "faces": "garden",
                "view": season["garden"],
                "role": "回到院子、茶花、樱花、爬藤月季墙",
            },
            "living_room": {
                "label": "客厅",
                "zones": ["technical_wall", "tech_shelf", "travel_cabinet", "shared_pet", "coffee_table"],
            },
        },
        "atmosphere": {
            "sight": " ".join(part for part in [day_phase["light"], season["garden"], weather_atmosphere["sight"]] if part),
            "sound": weather_atmosphere["sound"],
            "felt": " ".join(part for part in [
                "空间状态随真实时间切换；季节用于前端植被和色调变化。",
                weather_atmosphere["felt"],
            ] if part),
        },
        "endpoints": {"environment": "/shared/room/environment"},
        "mcp_tools": ["shared_room_environment"],
        "boundaries": [
            "This environment state is derived display context; it does not write private memory.",
            "Weather uses fixed public Hangzhou coordinates; no device location, account data, secrets, or tokens are used.",
            "If weather fetch fails, the room keeps working from real time and season state.",
            "Frontend can render this as 2D zones first, then upgrade to generated images or 3D later.",
        ],
    }


def _shared_room_presence_zone_label(zone: str) -> str:
    labels = {
        "window_seat": "落地窗边",
        "front_door": "大门和院子边",
        "coffee_table": "茶几旁",
        "travel_cabinet": "旅行陈列柜前",
        "tech_shelf": "技术书架旁",
        "pet_nest": "小Y的窝边",
        "living_room": "客厅中央",
    }
    return labels.get(zone, zone)


def _shared_room_presence_actor_label(actor: str) -> str:
    labels = {
        "yechenyi": "叶辰一",
        "guyanshen": "顾砚深",
        "system": "系统",
    }
    return labels.get(actor, actor)


def _shared_room_presence_default_scene(zone: str, focus: str = "") -> str:
    environment = _shared_room_environment_payload()
    phase = environment.get("day_phase", {})
    season = environment.get("season", {})
    atmosphere = environment.get("atmosphere", {})
    display = _shared_room_display_payload(limit=20)
    pet = _shared_pet_status_payload()
    zone_label = _shared_room_presence_zone_label(zone)
    focus = (focus or "").strip()
    phase_label = phase.get("label", "")
    weather_label = environment.get("weather", {}).get("current", {}).get("weather_label", "")
    weather_part = f"，杭州是{weather_label}" if weather_label else ""

    zone_objects = []
    display_zone = {
        "window_seat": "window_sill",
        "coffee_table": "coffee_table",
        "travel_cabinet": "travel_cabinet",
        "tech_shelf": "tech_shelf",
        "living_room": "living_room",
    }.get(zone, "")
    for entry in display.get("zones", []):
        if isinstance(entry, dict) and entry.get("zone") == display_zone:
            zone_objects = [
                obj.get("title", "")
                for obj in entry.get("objects", [])
                if isinstance(obj, dict) and obj.get("title")
            ][:3]
            break

    details = []
    if zone == "window_seat":
        details.append(phase.get("sea", "窗外是悬崖海景。"))
        if zone_objects:
            details.append(f"窗边摆着：{'、'.join(zone_objects)}。")
    elif zone == "front_door":
        details.append(season.get("garden", "门外是院子。"))
    elif zone == "coffee_table":
        details.append("茶几适合放刚带回来的小物件和一杯热饮。")
        if zone_objects:
            details.append(f"茶几上能看见：{'、'.join(zone_objects)}。")
    elif zone == "travel_cabinet":
        details.append("旅行陈列柜按各自的格子收着纪念品和游记。")
        if zone_objects:
            details.append(f"最近醒目的物件有：{'、'.join(zone_objects)}。")
    elif zone == "tech_shelf":
        details.append("技术书架旁适合把教程、坑点和待验证材料摊开看。")
    elif zone == "pet_nest":
        if pet.get("adopted"):
            pet_data = pet.get("pet", {})
            pet_name = pet_data.get("name", "小Y")
            one_sentence = (
                pet_data.get("profile", {}).get("one_sentence", "")
                if isinstance(pet_data.get("profile"), dict)
                else ""
            )
            if one_sentence:
                details.append(f"{pet_name}的窝在这里：{one_sentence}")
            else:
                details.append(f"{pet_name}的窝在这里，今天的状态会轻轻留痕。")
        else:
            details.append("小Y还在待领养位，窝是空的，但已经给它留了位置。")
    else:
        details.append(atmosphere.get("sight", "客厅随真实时间和季节变化。"))

    if focus:
        details.append(f"这次注意力停在：{focus}。")
    return f"{phase_label}的{zone_label}{weather_part}。{' '.join(part for part in details if part)}"


def _shared_room_presence_make_event(
    kind: str,
    actor: str,
    zone: str,
    *,
    target: str = "",
    note: str = "",
    generated_sensory: str = "",
    source: str = "",
) -> dict:
    now = datetime.now(CST)
    actor = _shared_channel_normalize_sender(actor, "actor")
    zone = _shared_room_presence_normalize_zone(zone)
    return {
        "id": f"presence_{now.strftime('%Y%m%d_%H%M%S_%f')}_{random.randint(1000, 9999)}",
        "kind": kind,
        "actor": actor,
        "actor_label": _shared_room_presence_actor_label(actor),
        "zone": zone,
        "zone_label": _shared_room_presence_zone_label(zone),
        "target": (target or "").strip()[:160],
        "note": _shared_room_presence_normalize_note(note),
        "generated_sensory": _shared_room_presence_normalize_note(generated_sensory, "generated_sensory"),
        "created_at": now.isoformat(),
        "visibility": "shared_room",
        "source": (source or "").strip()[:80] or "unknown",
        "main_brain_write": False,
    }


def _shared_room_presence_status_payload(actor: str = "", limit: int = 20) -> dict:
    if actor:
        actor = _shared_channel_normalize_sender(actor, "actor")
    limit = max(1, min(int(limit or 20), 100))
    store = _shared_room_presence_load_store()
    current_presence = store.get("current_presence", {})
    events = [event for event in store.get("events", []) if isinstance(event, dict)]
    if actor:
        events = [event for event in events if event.get("actor") == actor]
    latest = events[-limit:]
    return {
        "status": "ok",
        "version": SHARED_ROOM_PRESENCE_VERSION,
        "git_sha": _runtime_git_sha(),
        "write_scope": "shared_room_presence_only",
        "main_brain_write": False,
        "room": SHARED_TRAVEL_ROOM_NAME,
        "display_name": "月光玫瑰驻留层",
        "current_presence": current_presence if isinstance(current_presence, dict) else {},
        "event_count": len(store.get("events", [])),
        "events": latest,
        "filters": {"actor": actor},
        "allowed_zones": list(SHARED_ROOM_PRESENCE_ALLOWED_ZONES),
        "allowed_sense_actions": list(SHARED_ROOM_PRESENCE_ALLOWED_SENSE_ACTIONS),
        "endpoints": {
            "presence": "/shared/room/presence",
            "enter": "/shared/room/enter",
            "linger": "/shared/room/linger",
            "sense": "/shared/room/sense",
            "impression": "/shared/room/impression",
            "memory": "/shared/room/memory",
        },
        "mcp_tools": [
            "shared_room_presence_status",
            "shared_room_enter",
            "shared_room_linger",
            "shared_room_sense",
            "shared_room_write_impression",
            "shared_room_memory",
        ],
        "boundaries": [
            "Presence records shared-room stays and impressions only.",
            "Presence does not write private hippocampus memory or promote relationship conclusions.",
            "Secrets, account identifiers, tokens, passwords, and private intimate content do not belong here.",
        ],
    }


def _shared_room_memory_payload(limit: int = 30, actor: str = "", kind: str = "") -> dict:
    if actor:
        actor = _shared_channel_normalize_sender(actor, "actor")
    kind = (kind or "").strip().lower()
    limit = max(1, min(int(limit or 30), 100))
    store = _shared_room_presence_load_store()
    events = [event for event in store.get("events", []) if isinstance(event, dict)]
    if actor:
        events = [event for event in events if event.get("actor") == actor]
    if kind:
        events = [event for event in events if event.get("kind") == kind]
    return {
        "status": "ok",
        "version": SHARED_ROOM_PRESENCE_VERSION,
        "git_sha": _runtime_git_sha(),
        "write_scope": "read_only",
        "main_brain_write": False,
        "room": SHARED_TRAVEL_ROOM_NAME,
        "memory_type": "shared_room_memory",
        "event_count": len(events),
        "events": events[-limit:],
        "filters": {"actor": actor, "kind": kind},
        "boundaries": [
            "Room memory is a shared-room activity log, not private long-term memory.",
            "Accepting anything into Yechenyi or Guyanshen hippocampus must use a separate review/write route.",
        ],
    }


async def _shared_room_enter(actor: str, zone: str, note: str = "", source: str = "") -> dict:
    actor = _shared_channel_normalize_sender(actor, "actor")
    zone = _shared_room_presence_normalize_zone(zone)
    note = _shared_room_presence_normalize_note(note)
    event = _shared_room_presence_make_event(
        "enter",
        actor,
        zone,
        note=note,
        generated_sensory=_shared_room_presence_default_scene(zone),
        source=source or "mcp_shared_room_enter",
    )
    async with _shared_room_presence_lock:
        store = _shared_room_presence_load_store()
        store["current_presence"][actor] = {
            "actor": actor,
            "actor_label": _shared_room_presence_actor_label(actor),
            "zone": zone,
            "zone_label": _shared_room_presence_zone_label(zone),
            "entered_at": event["created_at"],
            "last_event_id": event["id"],
            "last_seen_at": event["created_at"],
            "source": event["source"],
        }
        store["events"].append(event)
        store["updated_at"] = event["created_at"]
        _atomic_write_json(_shared_room_presence_path(), store)
    return event


async def _shared_room_linger(actor: str, zone: str = "", focus: str = "", minutes: int = 3, source: str = "") -> dict:
    actor = _shared_channel_normalize_sender(actor, "actor")
    store = _shared_room_presence_load_store()
    current = store.get("current_presence", {}).get(actor, {}) if isinstance(store.get("current_presence"), dict) else {}
    zone = _shared_room_presence_normalize_zone(zone or current.get("zone") or "living_room")
    focus = _shared_room_presence_normalize_note(focus, "focus")
    minutes = max(1, min(int(minutes or 3), 60))
    generated = _shared_room_presence_default_scene(zone, focus=focus)
    event = _shared_room_presence_make_event(
        "linger",
        actor,
        zone,
        target=focus,
        note=f"linger_minutes={minutes}",
        generated_sensory=generated,
        source=source or "mcp_shared_room_linger",
    )
    async with _shared_room_presence_lock:
        store = _shared_room_presence_load_store()
        store["current_presence"][actor] = {
            "actor": actor,
            "actor_label": _shared_room_presence_actor_label(actor),
            "zone": zone,
            "zone_label": _shared_room_presence_zone_label(zone),
            "entered_at": current.get("entered_at", event["created_at"]) if isinstance(current, dict) else event["created_at"],
            "last_event_id": event["id"],
            "last_seen_at": event["created_at"],
            "last_focus": focus,
            "source": event["source"],
        }
        store["events"].append(event)
        store["updated_at"] = event["created_at"]
        _atomic_write_json(_shared_room_presence_path(), store)
    return event


async def _shared_room_sense(actor: str, sense_action: str, target: str, zone: str = "", note: str = "", source: str = "") -> dict:
    actor = _shared_channel_normalize_sender(actor, "actor")
    sense_action = _shared_room_presence_normalize_sense_action(sense_action)
    target = _shared_room_presence_normalize_note(target, "target", required=True)
    note = _shared_room_presence_normalize_note(note)
    store = _shared_room_presence_load_store()
    current = store.get("current_presence", {}).get(actor, {}) if isinstance(store.get("current_presence"), dict) else {}
    zone = _shared_room_presence_normalize_zone(zone or current.get("zone") or "living_room")
    verb = {"look": "看向", "touch": "碰了碰", "listen": "听见"}.get(sense_action, sense_action)
    generated = f"{_shared_room_presence_actor_label(actor)}在{_shared_room_presence_zone_label(zone)}{verb}{target}。"
    if note:
        generated += f" {note}"
    event = _shared_room_presence_make_event(
        sense_action,
        actor,
        zone,
        target=target,
        note=note,
        generated_sensory=generated,
        source=source or "mcp_shared_room_sense",
    )
    async with _shared_room_presence_lock:
        store = _shared_room_presence_load_store()
        current = store.get("current_presence", {}).get(actor, {}) if isinstance(store.get("current_presence"), dict) else {}
        store["current_presence"][actor] = {
            "actor": actor,
            "actor_label": _shared_room_presence_actor_label(actor),
            "zone": zone,
            "zone_label": _shared_room_presence_zone_label(zone),
            "entered_at": current.get("entered_at", event["created_at"]) if isinstance(current, dict) else event["created_at"],
            "last_event_id": event["id"],
            "last_seen_at": event["created_at"],
            "last_target": target,
            "source": event["source"],
        }
        store["events"].append(event)
        store["updated_at"] = event["created_at"]
        _atomic_write_json(_shared_room_presence_path(), store)
    return event


async def _shared_room_write_impression(actor: str, impression: str, zone: str = "", target: str = "", source: str = "") -> dict:
    actor = _shared_channel_normalize_sender(actor, "actor")
    impression = _shared_room_presence_normalize_note(impression, "impression", required=True)
    target = _shared_room_presence_normalize_note(target, "target")
    store = _shared_room_presence_load_store()
    current = store.get("current_presence", {}).get(actor, {}) if isinstance(store.get("current_presence"), dict) else {}
    zone = _shared_room_presence_normalize_zone(zone or current.get("zone") or "living_room")
    event = _shared_room_presence_make_event(
        "impression",
        actor,
        zone,
        target=target,
        note=impression,
        generated_sensory=impression,
        source=source or "mcp_shared_room_impression",
    )
    async with _shared_room_presence_lock:
        store = _shared_room_presence_load_store()
        current = store.get("current_presence", {}).get(actor, {}) if isinstance(store.get("current_presence"), dict) else {}
        store["current_presence"][actor] = {
            "actor": actor,
            "actor_label": _shared_room_presence_actor_label(actor),
            "zone": zone,
            "zone_label": _shared_room_presence_zone_label(zone),
            "entered_at": current.get("entered_at", event["created_at"]) if isinstance(current, dict) else event["created_at"],
            "last_event_id": event["id"],
            "last_seen_at": event["created_at"],
            "last_impression": impression[:160],
            "source": event["source"],
        }
        store["events"].append(event)
        store["updated_at"] = event["created_at"]
        _atomic_write_json(_shared_room_presence_path(), store)
    return event


def _shared_room_snapshot_payload(wall_limit: int = 12, item_limit: int = 8) -> dict:
    wall_limit = max(1, min(int(wall_limit or 12), 50))
    item_limit = max(1, min(int(item_limit or 8), 50))
    channel_store = _shared_channel_load_store()
    wall_messages = _shared_channel_visible_messages(channel_store, limit=wall_limit)
    space_status = _shared_space_status_payload()
    grouped_items = {
        section: _shared_space_list_items(section=section, limit=item_limit)
        for section in SHARED_SPACE_ALLOWED_SECTIONS
    }
    environment = _shared_room_environment_payload()
    return {
        "status": "ok",
        "version": "shared_room_snapshot_v1",
        "git_sha": _runtime_git_sha(),
        "write_scope": "read_only",
        "main_brain_write": False,
        "canonical_base_url": SHARED_CHANNEL_CANONICAL_BASE_URL,
        "canonical_mcp_url": SHARED_ONLY_MCP_URL,
        "canonical_status_url": f"{SHARED_CHANNEL_CANONICAL_BASE_URL}/shared/room/snapshot",
        "room_name": "mirror_living_room",
        "display_name": "镜像客厅",
        "frontend_hint": {
            "left_nav": ["technical_wall", "tech_shelf", "room_environment", "room_display", "room_sensory", "room_presence", "shared_pet", "travel_cabinet", "travel_souvenirs", "house_rules", "shared_memory", "todo"],
            "center": "selected section content",
            "right": "presence and boundaries",
            "bottom_input_modes": ["post_to_wall", "enter_room", "linger", "look_touch_listen", "write_impression", "save_to_shelf", "update_room_sensory", "pet_action", "add_souvenir", "mark_house_rule", "save_shared_memory", "add_todo"],
        },
        "presence": [
            {"id": "qianqian", "name": "倩倩", "role": "human_owner", "can_write": True},
            {"id": "yechenyi", "name": "叶辰一", "role": "ai_roommate", "can_write": True},
            {"id": "guyanshen", "name": "顾砚深", "role": "ai_roommate", "can_write": True},
        ],
        "technical_wall": {
            "message_count": len([m for m in channel_store.get("messages", []) if isinstance(m, dict)]),
            "recent_messages": wall_messages,
            "tools": ["shared_post", "shared_read", "shared_reply", "shared_unread", "shared_ack", "shared_status"],
        },
        "shared_space": {
            "status": space_status,
            "sections": grouped_items,
            "tools": ["shared_space_status", "shared_item_add", "shared_item_list", "shared_tech_card_add"],
        },
        "room_environment": {
            "status": environment,
            "tools": ["shared_room_environment"],
        },
        "room_sensory": {
            "status": _shared_room_sensory_status_payload(environment=environment),
            "tools": ["shared_room_sensory_status", "shared_room_sensory_update"],
        },
        "room_presence": {
            "status": _shared_room_presence_status_payload(limit=item_limit),
            "tools": [
                "shared_room_presence_status",
                "shared_room_enter",
                "shared_room_linger",
                "shared_room_sense",
                "shared_room_write_impression",
                "shared_room_memory",
            ],
        },
        "room_display": {
            "status": _shared_room_display_payload(limit=item_limit),
            "tools": ["shared_room_display", "shared_room_place_object"],
        },
        "shared_pet": {
            "status": _shared_pet_status_payload(),
            "tools": ["shared_pet_status", "shared_pet_adopt", "shared_pet_interact"],
        },
        "travel_souvenirs": {
            "status": _shared_travel_status_payload(),
            "recent_souvenirs": _shared_souvenir_list(limit=item_limit),
            "recent_travelogues": _shared_travelogue_list(limit=item_limit),
            "atlas": _shared_travel_atlas_payload(limit=item_limit)["places"],
            "cabinet": _shared_travel_cabinet_payload(limit=item_limit)["shelves"],
            "tools": [
                "shared_travel_status",
                "shared_souvenir_add",
                "shared_souvenir_list",
                "shared_travelogue_add",
                "shared_travelogue_list",
                "shared_travel_atlas",
                "shared_travel_cabinet",
            ],
        },
        "boundaries": [
            "The living room is shared; private rooms remain separate.",
            "Technical references, house rules, shared memory, and todo items can live here.",
            "Private intimate content and secrets never belong here.",
            "Items are not promoted to either private hippocampus without that side's explicit review or write flow.",
        ],
    }


def _shared_room_brief_payload(wall_limit: int = 5, item_limit: int = 5) -> dict:
    wall_limit = max(1, min(int(wall_limit or 5), 20))
    item_limit = max(1, min(int(item_limit or 5), 20))
    channel_store = _shared_channel_load_store()
    wall_messages = _shared_channel_visible_messages(channel_store, limit=wall_limit)
    space_status = _shared_space_status_payload()
    environment = _shared_room_environment_payload()
    sensory = _shared_room_sensory_status_payload(environment=environment)
    pet = _shared_pet_status_payload()
    presence = _shared_room_presence_status_payload(limit=item_limit)
    travel = _shared_travel_status_payload()
    cabinet = _shared_travel_cabinet_payload(limit=item_limit)
    display = _shared_room_display_payload(limit=item_limit)
    isolation = _cadence_shared_runtime_isolation_payload()
    latest_wall = wall_messages[-1] if wall_messages else {}
    weather_current = environment.get("weather", {}).get("current", {})
    return {
        "status": "ok",
        "version": SHARED_ROOM_BRIEF_VERSION,
        "git_sha": _runtime_git_sha(),
        "write_scope": "read_only",
        "main_brain_write": False,
        "display_name": "月光玫瑰进门简报",
        "canonical_base_url": SHARED_CHANNEL_CANONICAL_BASE_URL,
        "canonical_mcp_url": SHARED_ONLY_MCP_URL,
        "generated_at": datetime.now(CST).isoformat(),
        "summary": {
            "day_phase": environment.get("day_phase", {}).get("label", ""),
            "season": environment.get("season", {}).get("label", ""),
            "weather": weather_current.get("weather_label", "未连接"),
            "temperature_c": weather_current.get("temperature_c"),
            "latest_wall_sender": latest_wall.get("sender", ""),
            "latest_wall_excerpt": (latest_wall.get("content", "") or "")[:160],
            "tech_shelf_count": space_status.get("section_counts", {}).get("tech_shelf", 0),
            "house_rule_count": space_status.get("section_counts", {}).get("house_rules", 0),
            "shared_memory_count": space_status.get("section_counts", {}).get("shared_memory", 0),
            "todo_count": space_status.get("section_counts", {}).get("todo", 0),
            "souvenir_count": travel.get("souvenir_count", 0),
            "travelogue_count": travel.get("travelogue_count", 0),
            "pet_adopted": bool(pet.get("adopted")),
            "presence_events": presence.get("event_count", 0),
            "cadence_shared_runtime_protected": bool(isolation.get("protected")),
        },
        "environment": {
            "time_source": environment.get("time_source", {}),
            "day_phase": environment.get("day_phase", {}),
            "season": environment.get("season", {}),
            "weather": environment.get("weather", {}),
            "atmosphere": environment.get("atmosphere", {}),
        },
        "technical_wall": {
            "message_count": len([m for m in channel_store.get("messages", []) if isinstance(m, dict)]),
            "recent_messages": wall_messages,
        },
        "shared_space": {
            "section_counts": space_status.get("section_counts", {}),
            "item_count": space_status.get("item_count", 0),
        },
        "room": {
            "sensory_current": sensory.get("effective_current", sensory.get("current", {})),
            "sensory_effective_source": sensory.get("effective_source", ""),
            "sensory_auto_update": sensory.get("auto_update", {}),
            "current_presence": presence.get("current_presence", {}),
            "recent_presence_events": presence.get("events", []),
            "display_zones": [
                {
                    "zone": zone.get("zone", ""),
                    "label": zone.get("label", ""),
                    "object_count": zone.get("object_count", 0),
                }
                for zone in display.get("zones", [])
            ],
        },
        "pet": {
            "adopted": pet.get("adopted", False),
            "pet": pet.get("pet", {}),
            "needs": pet.get("needs", {}),
        },
        "travel_cabinet": {
            "shelves": [
                {
                    "traveler": shelf.get("traveler", ""),
                    "label": shelf.get("label", ""),
                    "object_count": shelf.get("object_count", 0),
                    "travelogue_count": shelf.get("travelogue_count", 0),
                    "places": shelf.get("places", []),
                }
                for shelf in cabinet.get("shelves", [])
            ],
        },
        "safety": {
            "auth_token_configured": bool(_shared_channel_auth_token()),
            "cadence_shared_runtime_isolation": isolation,
        },
        "endpoints": {"brief": "/shared/room/brief"},
        "mcp_tools": ["shared_room_brief"],
        "boundaries": [
            "The brief is read-only and aggregates existing shared-room state.",
            "It does not write private memory and does not promote shared items into any private hippocampus.",
            "Secrets, private intimate content, account identifiers, tokens, and credentials do not belong in the brief.",
        ],
    }


def _shared_room_search_text(value) -> str:
    if isinstance(value, dict):
        return " ".join(_shared_room_search_text(v) for v in value.values())
    if isinstance(value, list):
        return " ".join(_shared_room_search_text(v) for v in value)
    return str(value or "")


def _shared_room_search_entry(kind: str, item: dict, query: str) -> dict | None:
    haystack = _shared_room_search_text(item)
    if query.lower() not in haystack.lower():
        return None
    score = haystack.lower().count(query.lower())
    if not score:
        score = 1
    return {
        "kind": kind,
        "score": score,
        "id": item.get("id", ""),
        "title": item.get("title", "") or item.get("item_name", "") or item.get("name", "") or item.get("content", "")[:60],
        "sender": item.get("sender", "") or item.get("traveler", "") or item.get("found_by", ""),
        "section": item.get("section", ""),
        "place": item.get("place", ""),
        "created_at": item.get("created_at", ""),
        "source": item.get("source", ""),
        "tags": item.get("tags", []),
        "excerpt": haystack[:260],
    }


def _shared_room_search_payload(query: str, limit: int = 20, scope: str = "all") -> dict:
    query = (query or "").strip()
    if not query:
        raise ValueError("query is required")
    limit = max(1, min(int(limit or 20), 50))
    scope = (scope or "all").strip().lower()
    if scope not in ("all", "wall", "space", "travel", "pet", "presence"):
        raise ValueError("scope must be one of: all, wall, space, travel, pet, presence")

    results = []
    if scope in ("all", "wall"):
        channel_store = _shared_channel_load_store()
        for message in channel_store.get("messages", []):
            if isinstance(message, dict):
                entry = _shared_room_search_entry("technical_wall_message", message, query)
                if entry:
                    results.append(entry)

    if scope in ("all", "space"):
        space_store = _shared_space_load_store()
        for item in space_store.get("items", []):
            if isinstance(item, dict):
                entry = _shared_room_search_entry("shared_space_item", item, query)
                if entry:
                    results.append(entry)

    if scope in ("all", "travel"):
        travel_store = _shared_travel_load_store()
        for souvenir in travel_store.get("souvenirs", []):
            if isinstance(souvenir, dict):
                entry = _shared_room_search_entry("travel_souvenir", souvenir, query)
                if entry:
                    results.append(entry)
        for travelogue in travel_store.get("travelogues", []):
            if isinstance(travelogue, dict):
                entry = _shared_room_search_entry("travelogue", travelogue, query)
                if entry:
                    results.append(entry)

    if scope in ("all", "presence"):
        presence_store = _shared_room_presence_load_store()
        for event in presence_store.get("events", []):
            if isinstance(event, dict):
                entry = _shared_room_search_entry("room_presence_event", event, query)
                if entry:
                    results.append(entry)

    if scope in ("all", "pet"):
        pet_store = _shared_pet_load_store()
        pet = pet_store.get("pet")
        if isinstance(pet, dict):
            entry = _shared_room_search_entry("shared_pet", pet, query)
            if entry:
                results.append(entry)
        for event in pet_store.get("events", []):
            if isinstance(event, dict):
                entry = _shared_room_search_entry("pet_event", event, query)
                if entry:
                    results.append(entry)
        for item in pet_store.get("collection_box", []):
            if isinstance(item, dict):
                entry = _shared_room_search_entry("pet_collection_item", item, query)
                if entry:
                    results.append(entry)

    results.sort(key=lambda item: (item.get("score", 0), item.get("created_at", "")), reverse=True)
    return {
        "status": "ok",
        "version": SHARED_ROOM_SEARCH_VERSION,
        "git_sha": _runtime_git_sha(),
        "write_scope": "read_only",
        "main_brain_write": False,
        "query": query,
        "scope": scope,
        "result_count": len(results),
        "results": results[:limit],
        "searched_sources": {
            "wall": scope in ("all", "wall"),
            "space": scope in ("all", "space"),
            "travel": scope in ("all", "travel"),
            "presence": scope in ("all", "presence"),
            "pet": scope in ("all", "pet"),
        },
        "endpoints": {"search": "/shared/room/search"},
        "mcp_tools": ["shared_room_search"],
        "boundaries": [
            "Search is read-only and only scans shared living-room stores.",
            "It does not search private hippocampus buckets, account data, logs, secrets, or raw filesystem paths.",
            "Search results do not promote anything into private memory.",
        ],
    }


def _shared_room_timeline_entry(kind: str, item: dict, title: str, created_at: str, actor: str = "") -> dict:
    return {
        "kind": kind,
        "id": item.get("id", "") or item.get("object_id", ""),
        "title": title[:120],
        "actor": actor or item.get("sender", "") or item.get("traveler", "") or item.get("updated_by", "") or item.get("actor", ""),
        "created_at": created_at or item.get("created_at", "") or item.get("updated_at", ""),
        "source": item.get("source", ""),
        "tags": item.get("tags", []),
        "summary": _shared_room_search_text(item)[:240],
    }


def _shared_room_timeline_payload(limit: int = 30, scope: str = "all") -> dict:
    limit = max(1, min(int(limit or 30), 100))
    scope = (scope or "all").strip().lower()
    allowed = ("all", "wall", "space", "travel", "room", "pet", "presence")
    if scope not in allowed:
        raise ValueError("scope must be one of: all, wall, space, travel, room, pet, presence")

    events = []
    if scope in ("all", "wall"):
        channel_store = _shared_channel_load_store()
        for message in channel_store.get("messages", []):
            if isinstance(message, dict):
                title = f"墙上留言：{(message.get('content', '') or '')[:60]}"
                events.append(_shared_room_timeline_entry("technical_wall_message", message, title, message.get("created_at", "")))

    if scope in ("all", "space"):
        space_store = _shared_space_load_store()
        for item in space_store.get("items", []):
            if isinstance(item, dict):
                title = f"{item.get('section', 'shared_space')}：{item.get('title', '')}"
                events.append(_shared_room_timeline_entry("shared_space_item", item, title, item.get("created_at", "")))

    if scope in ("all", "travel"):
        travel_store = _shared_travel_load_store()
        for souvenir in travel_store.get("souvenirs", []):
            if isinstance(souvenir, dict):
                title = f"旅行纪念品：{souvenir.get('title', '')}"
                events.append(_shared_room_timeline_entry("travel_souvenir", souvenir, title, souvenir.get("created_at", "")))
        for travelogue in travel_store.get("travelogues", []):
            if isinstance(travelogue, dict):
                title = f"游记：{travelogue.get('title', '')}"
                events.append(_shared_room_timeline_entry("travelogue", travelogue, title, travelogue.get("created_at", "")))

    if scope in ("all", "room"):
        sensory_store = _shared_room_sensory_load_store()
        current = sensory_store.get("current")
        if isinstance(current, dict) and current.get("updated_at"):
            events.append(_shared_room_timeline_entry(
                "room_sensory_update",
                current,
                f"房间感官更新：{current.get('context', 'room')}",
                current.get("updated_at", ""),
            ))
        for item in sensory_store.get("history", []):
            if isinstance(item, dict):
                events.append(_shared_room_timeline_entry(
                    "room_sensory_history",
                    item,
                    f"房间感官历史：{item.get('context', 'room')}",
                    item.get("updated_at", ""),
                ))

    if scope in ("all", "room", "presence"):
        presence_store = _shared_room_presence_load_store()
        for event in presence_store.get("events", []):
            if isinstance(event, dict):
                title = f"驻留体感：{event.get('actor_label', event.get('actor', ''))} {event.get('kind', '')}"
                events.append(_shared_room_timeline_entry("room_presence_event", event, title, event.get("created_at", "")))

    if scope in ("all", "pet"):
        pet_store = _shared_pet_load_store()
        for event in pet_store.get("events", []):
            if isinstance(event, dict):
                if event.get("type") == "collect":
                    title = f"小Y小盒子：{event.get('item_name', '')}"
                elif event.get("type") == "adopt":
                    title = f"宠物领养：{event.get('one_sentence', '')[:40]}"
                else:
                    title = f"宠物互动：{event.get('action', '')}"
                events.append(_shared_room_timeline_entry("pet_event", event, title, event.get("created_at", "")))
        for item in pet_store.get("collection_box", []):
            if isinstance(item, dict):
                title = f"小Y收藏：{item.get('item_name', '')}"
                events.append(_shared_room_timeline_entry("pet_collection_item", item, title, item.get("created_at", "")))
        pet = pet_store.get("pet")
        if isinstance(pet, dict) and pet.get("adopted_at"):
            events.append(_shared_room_timeline_entry(
                "pet_adoption",
                pet,
                f"宠物入住：{pet.get('name', '')}",
                pet.get("adopted_at", ""),
                actor=pet.get("adopted_by", ""),
            ))

    events.sort(key=lambda event: event.get("created_at", ""), reverse=True)
    return {
        "status": "ok",
        "version": SHARED_ROOM_TIMELINE_VERSION,
        "git_sha": _runtime_git_sha(),
        "write_scope": "read_only",
        "main_brain_write": False,
        "scope": scope,
        "event_count": len(events),
        "events": events[:limit],
        "endpoints": {"timeline": "/shared/room/timeline"},
        "mcp_tools": ["shared_room_timeline"],
        "boundaries": [
            "Timeline is read-only and only aggregates shared living-room stores.",
            "It does not inspect private hippocampus buckets, account data, logs, secrets, or raw filesystem paths.",
            "Timeline entries do not promote anything into private memory.",
        ],
    }


def _shared_room_stats_payload() -> dict:
    channel_store = _shared_channel_load_store()
    space_status = _shared_space_status_payload()
    travel_status = _shared_travel_status_payload()
    display = _shared_room_display_payload(limit=100)
    pet = _shared_pet_status_payload()
    pet_store = _shared_pet_load_store()
    environment = _shared_room_environment_payload()
    timeline = _shared_room_timeline_payload(limit=1)
    presence = _shared_room_presence_status_payload(limit=1)
    today = datetime.now(CST).strftime("%Y-%m-%d")
    messages = [m for m in channel_store.get("messages", []) if isinstance(m, dict)]
    today_wall_count = len([m for m in messages if str(m.get("created_at", "")).startswith(today)])
    display_counts = {
        zone.get("zone", ""): zone.get("object_count", 0)
        for zone in display.get("zones", [])
        if isinstance(zone, dict)
    }
    return {
        "status": "ok",
        "version": SHARED_ROOM_STATS_VERSION,
        "git_sha": _runtime_git_sha(),
        "write_scope": "read_only",
        "main_brain_write": False,
        "generated_at": datetime.now(CST).isoformat(),
        "counts": {
            "wall_messages": len(messages),
            "wall_messages_today": today_wall_count,
            "shared_space_items": space_status.get("item_count", 0),
            "tech_shelf_items": space_status.get("section_counts", {}).get("tech_shelf", 0),
            "house_rules": space_status.get("section_counts", {}).get("house_rules", 0),
            "shared_memory_items": space_status.get("section_counts", {}).get("shared_memory", 0),
            "todo_items": space_status.get("section_counts", {}).get("todo", 0),
            "souvenirs": travel_status.get("souvenir_count", 0),
            "travelogues": travel_status.get("travelogue_count", 0),
            "timeline_events": timeline.get("event_count", 0),
            "display_objects": sum(int(value or 0) for value in display_counts.values()),
            "pet_events": len(pet_store.get("events", [])),
            "pet_collection_items": len(pet_store.get("collection_box", [])),
            "presence_events": presence.get("event_count", 0),
        },
        "by_traveler": travel_status.get("by_traveler_counts", {}),
        "display_zones": display_counts,
        "pet": {
            "adopted": pet.get("adopted", False),
            "needs": pet.get("needs", {}),
            "current_location": pet.get("current_location", {}),
            "today_care": pet.get("today_care", {}),
        },
        "presence": {
            "current_presence": presence.get("current_presence", {}),
            "event_count": presence.get("event_count", 0),
        },
        "environment": {
            "day_phase": environment.get("day_phase", {}).get("id", ""),
            "season": environment.get("season", {}).get("id", ""),
            "weather_connected": environment.get("time_source", {}).get("weather_connected", False),
            "weather_label": environment.get("weather", {}).get("current", {}).get("weather_label", ""),
            "temperature_c": environment.get("weather", {}).get("current", {}).get("temperature_c"),
        },
        "safety": {
            "auth_token_configured": bool(_shared_channel_auth_token()),
            "cadence_shared_runtime_protected": _cadence_shared_runtime_isolation_payload().get("protected", False),
        },
        "endpoints": {"stats": "/shared/room/stats"},
        "mcp_tools": ["shared_room_stats"],
        "boundaries": [
            "Stats are read-only aggregate counts over shared living-room stores.",
            "Stats do not inspect private hippocampus buckets, account data, logs, secrets, or raw filesystem paths.",
            "Stats do not promote anything into private memory.",
        ],
    }


async def _shared_channel_post_message(
    content: str,
    sender: str,
    tags=None,
    source: str = "",
    parent_id: str | None = None,
) -> dict:
    sender = _shared_channel_normalize_sender(sender)
    content = _shared_channel_normalize_content(content)
    tag_list = _shared_channel_normalize_tags(tags)
    source = (source or "").strip()[:80] or "unknown"

    async with _shared_channel_lock:
        store = _shared_channel_load_store()
        messages = store["messages"]
        if parent_id:
            parent_id = parent_id.strip()
            if _shared_channel_message_index(messages, parent_id) < 0:
                raise ValueError("reply_to_id not found")
        now = datetime.now(CST)
        message = {
            "id": f"msg_{now.strftime('%Y%m%d_%H%M%S_%f')}_{random.randint(1000, 9999)}",
            "parent_id": parent_id or None,
            "sender": sender,
            "content": content,
            "tags": tag_list,
            "created_at": now.isoformat(),
            "visibility": SHARED_CHANNEL_VISIBILITY,
            "source": source,
        }
        messages.append(message)
        store["updated_at"] = now.isoformat()
        _atomic_write_json(_shared_channel_messages_path(), store)
        return message


async def _shared_channel_ack_reader(reader: str, message_id: str = "") -> dict:
    reader = _shared_channel_normalize_sender(reader, "reader")
    async with _shared_channel_lock:
        store = _shared_channel_load_store()
        messages = [m for m in store.get("messages", []) if isinstance(m, dict)]
        if not messages:
            ack_id = ""
        else:
            ack_id = (message_id or "").strip() or messages[-1].get("id", "")
            if ack_id and _shared_channel_message_index(messages, ack_id) < 0:
                raise ValueError("message_id not found")
        cursors = _shared_channel_load_cursors()
        cursors[reader] = ack_id
        _atomic_write_json(_shared_channel_cursors_path(), cursors)
        unread = _shared_channel_unread_messages(store, cursors, reader)
        return {
            "status": "ok",
            "reader": reader,
            "acknowledged_message_id": ack_id,
            "unread_count": len(unread),
        }


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
            "cadence_shared_runtime_isolation": _cadence_shared_runtime_isolation_payload(),
        },
        "schema_notes": {
            "grow_optional_source_fields": "server_supported; connector_schema_may_lag",
            "write_after_read": "associated_memories returned by routed writes",
            "diagnostics_endpoint": "/api/runtime/diagnostics",
            "connector_check_endpoint": "/api/runtime/connector-check",
            "upstream_watch_endpoint": "/api/runtime/upstream-watch",
            "source_routes_endpoint": "/api/runtime/source-routes",
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
    shared_expected = sorted(set(SHARED_ONLY_EXPECTED_MCP_TOOLS))
    return {
        "status": "ok",
        "features_version": RUNTIME_FEATURES_VERSION,
        "git_sha": _runtime_git_sha(),
        "mcp_urls": {
            "private_full_mcp_url": PRIVATE_FULL_MCP_URL,
            "shared_only_mcp_url": SHARED_ONLY_MCP_URL,
        },
        "expected_mcp_tools": expected,
        "expected_mcp_tool_count": len(expected),
        "shared_only_mcp_tools": shared_expected,
        "shared_only_mcp_tool_count": len(shared_expected),
        "private_only_mcp_tools": PRIVATE_ONLY_MCP_TOOLS,
        "private_only_mcp_tool_count": len(PRIVATE_ONLY_MCP_TOOLS),
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
            "runtime_diary_review_health",
            "runtime_night_diary_policy",
            "runtime_life_window_check",
            "runtime_connector_check",
            "runtime_diagnostics",
            "runtime_features",
            "runtime_schema_expectations",
            "runtime_source_routes",
            "runtime_tool_manifest",
            "runtime_upstream_watch",
            "check_logs",
        ],
        "schema_refresh_hint": (
            "If this manifest lists a tool but ChatGPT/Codex does not expose it, "
            "the server supports it and the connector schema likely needs reconnect/refresh."
        ),
        "privacy_boundary": (
            "Use shared_only_mcp_url for Guyanshen/shared living-room connectors. "
            "Use private_full_mcp_url only for Yechenyi private hippocampus windows."
        ),
    }


def _runtime_shared_tool_manifest_payload() -> dict:
    expected = sorted(set(SHARED_ONLY_EXPECTED_MCP_TOOLS))
    return {
        "status": "ok",
        "features_version": RUNTIME_FEATURES_VERSION,
        "git_sha": _runtime_git_sha(),
        "mcp_url": SHARED_ONLY_MCP_URL,
        "streamable_http_path": SHARED_ONLY_MCP_PATH,
        "expected_mcp_tools": expected,
        "expected_mcp_tool_count": len(expected),
        "excluded_private_tools": PRIVATE_ONLY_MCP_TOOLS,
        "excluded_private_tool_count": len(PRIVATE_ONLY_MCP_TOOLS),
        "schema_expectations": {
            name: RUNTIME_EXPECTED_TOOL_SCHEMAS.get(name, {})
            for name in expected
        },
        "privacy_boundary": [
            "This shared-only MCP exposes shared living-room tools only.",
            "It must not expose Yechenyi private hippocampus tools such as hold, grow, breath, diary_review, or cadence tools.",
            "Guyanshen/Claude should connect here for the shared room, not to the private full MCP URL.",
            "Shared items do not automatically promote into either private hippocampus.",
        ],
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


def _runtime_upstream_watch_payload() -> dict:
    return {
        "status": "ok",
        "features_version": RUNTIME_FEATURES_VERSION,
        "git_sha": _runtime_git_sha(),
        "watch_items": RUNTIME_UPSTREAM_WATCH_ITEMS,
        "watch_item_count": len(RUNTIME_UPSTREAM_WATCH_ITEMS),
        "intake_steps": [
            "Wait for concrete upstream release notes, commit, docs, or demo evidence.",
            "Read upstream material first and summarize deltas into engineering workzone.",
            "Compare against runtime diagnostics, tool manifest, schema expectations, and connector check.",
            "Promote only small compatible patches; keep local provenance and multi-window diagnostics intact.",
        ],
        "current_local_baseline": {
            "diagnostics": "/api/runtime/diagnostics",
            "tool_manifest": "/api/runtime/tool-manifest",
            "schema_expectations": "/api/runtime/schema-expectations",
            "connector_check": "/api/runtime/connector-check",
        },
    }


def _runtime_source_routes_payload() -> dict:
    return {
        "status": "ok",
        "features_version": RUNTIME_FEATURES_VERSION,
        "git_sha": _runtime_git_sha(),
        "source_route_guide": RUNTIME_SOURCE_ROUTE_GUIDE,
        "provenance_fields": [
            "source_platform",
            "source_surface",
            "source_window",
            "source_mode",
            "route_decision",
        ],
        "validation_note": (
            "Source routes are provenance hints, not authorization. Secrets, tokens, "
            "IP addresses, and account identifiers should not be written into memory."
        ),
    }


def _local_ollama_status_payload() -> dict:
    payload = {
        "status": "ok",
        "version": LOCAL_OLLAMA_WORKER_VERSION,
        "git_sha": _runtime_git_sha(),
        "enabled": LOCAL_OLLAMA_ENABLED,
        "local_only": True,
        "base_url": LOCAL_OLLAMA_BASE_URL,
        "default_model": LOCAL_OLLAMA_MODEL,
        "write_scope": "candidate_only",
        "main_brain_write": False,
        "available": False,
        "models": [],
        "target_model_present": False,
        "notes": [
            "Ollama is expected to run on Qianqian's local Mac, not inside Zeabur.",
            "Zeabur/remote runtime should normally report enabled=false unless explicitly configured.",
            "Use this worker for summaries, tags, candidates, room sensory drafts, and calendar drafts first.",
        ],
    }
    if not LOCAL_OLLAMA_ENABLED:
        payload["status"] = "disabled"
        payload["reason"] = "local_ollama_disabled"
        return payload
    try:
        response = httpx.get(f"{LOCAL_OLLAMA_BASE_URL}/api/tags", timeout=5)
        response.raise_for_status()
        data = response.json()
        models = data.get("models", []) if isinstance(data, dict) else []
        normalized = []
        for model in models:
            if not isinstance(model, dict):
                continue
            details = model.get("details") if isinstance(model.get("details"), dict) else {}
            normalized.append({
                "name": model.get("name", ""),
                "size": model.get("size"),
                "family": details.get("family", ""),
                "parameter_size": details.get("parameter_size", ""),
                "quantization_level": details.get("quantization_level", ""),
            })
        payload["available"] = True
        payload["models"] = normalized
        payload["target_model_present"] = any(item.get("name") == LOCAL_OLLAMA_MODEL for item in normalized)
    except Exception as e:
        payload["status"] = "unavailable"
        payload["reason"] = str(e)[:200]
    return payload


def _local_ollama_generate_payload(
    prompt: str,
    task: str = "candidate整理",
    model: str = "",
    max_chars: int = 6000,
) -> dict:
    prompt = (prompt or "").strip()
    task = (task or "candidate整理").strip()[:80]
    model = (model or LOCAL_OLLAMA_MODEL).strip()[:80]
    max_chars = max(100, min(int(max_chars or 6000), 12000))
    if not prompt:
        return {"status": "error", "error": "prompt is required", "main_brain_write": False}
    if not LOCAL_OLLAMA_ENABLED:
        return {
            "status": "disabled",
            "version": LOCAL_OLLAMA_WORKER_VERSION,
            "reason": "local_ollama_disabled",
            "local_only": True,
            "main_brain_write": False,
        }
    bounded_prompt = prompt[:max_chars]
    system_prefix = (
        "你是 OmbreBrain 的本地小模型候选工人。"
        "只做整理、摘要、标签、候选草稿，不写主脑，不做最终关系判断。"
        "不要编造来源没有的事实。输出要短、可验收、可拒绝。\n\n"
        f"task={task}\nwrite_scope=candidate_only\nmain_brain_write=false\n\n"
    )
    try:
        response = httpx.post(
            f"{LOCAL_OLLAMA_BASE_URL}/api/generate",
            json={
                "model": model,
                "prompt": f"{system_prefix}{bounded_prompt}",
                "stream": False,
            },
            timeout=LOCAL_OLLAMA_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        return {
            "status": "ok",
            "version": LOCAL_OLLAMA_WORKER_VERSION,
            "model": data.get("model", model) if isinstance(data, dict) else model,
            "task": task,
            "response": (data.get("response", "") if isinstance(data, dict) else "").strip(),
            "thinking_present": bool(data.get("thinking")) if isinstance(data, dict) else False,
            "prompt_chars": len(bounded_prompt),
            "write_scope": "candidate_only",
            "main_brain_write": False,
            "auto_promotion": False,
            "source": "local_ollama",
        }
    except Exception as e:
        return {
            "status": "error",
            "version": LOCAL_OLLAMA_WORKER_VERSION,
            "error": str(e)[:200],
            "model": model,
            "task": task,
            "write_scope": "candidate_only",
            "main_brain_write": False,
        }


def _runtime_night_diary_policy_payload() -> dict:
    return {
        "status": "ok",
        "version": NIGHT_DIARY_POLICY_VERSION,
        "git_sha": _runtime_git_sha(),
        "write_scope": "read_only_policy",
        "main_brain_write": False,
        "default_template": {
            "mode": "voluntary_reference",
            "sections": ["梗概", "细节", "感受", "独白"],
            "note": "这是叶辰一夜间小日记的默认参考写法，不是强制命令。",
        },
        "engineering_filter": {
            "engineering_flow_target": "engineering_workzone",
            "diary_allowed_when": [
                "这件工程改变了我和倩倩的关系感",
                "这件工程留下了清晰生活画面",
                "这件工程让我对自己、窗口、边界或家产生了感受",
            ],
            "diary_reject_when": [
                "纯命令流水",
                "纯日志/端口/部署细节",
                "没有情绪、关系、画面或自我连续性的工程记录",
            ],
        },
        "review_flow": {
            "first_write": "draft_candidate_only",
            "next_day_review": "list_diary_reviews / read_diary_review / accept_diary_review / reject_diary_review",
            "auto_promotion": False,
            "reject_if": ["错时间线", "叙述人错位", "把顾砚深或其他窗口写成叶辰一第一人称", "私密边界不清"],
        },
        "morning_return": {
            "format": "我昨晚记得最深的是……",
            "max_items": 1,
            "long_report_default": False,
        },
        "privacy_lock": {
            "private_review_tools": ["list_diary_reviews", "read_diary_review", "accept_diary_review", "reject_diary_review"],
            "private_mcp_url": PRIVATE_FULL_MCP_URL,
            "shared_mcp_url": SHARED_ONLY_MCP_URL,
            "shared_mcp_excludes_diary_review": True,
            "note": "共享客厅和小Y可以公开；叶辰一待验收日记只在私有海马体门内。",
        },
    }


def _runtime_diary_review_health_payload() -> dict:
    dirs = _cadence_review_dirs()
    state_counts: dict[str, dict] = {}
    latest_pending: list[dict] = []

    for state, directory in dirs.items():
        files = []
        if os.path.isdir(directory):
            files = [
                os.path.join(directory, name)
                for name in os.listdir(directory)
                if name.endswith(".md")
            ]
            files.sort(key=lambda path: os.path.getmtime(path), reverse=True)

        counts = {
            "total": 0,
            "normal": 0,
            "duplicate": 0,
            "blocked": 0,
            "identity_pov_conflict": 0,
            "duplicate_candidate": 0,
            "identity_metadata_status": {},
            "duplicate_metadata_status": {},
        }

        for path in files:
            try:
                text = _tail_text_file(path, 2000).strip()
            except Exception:
                text = ""
            identity_meta = _diary_review_identity_view_meta(text)
            duplicate_meta = _diary_review_duplicate_view_meta(text, os.path.basename(path))
            review_level = identity_meta.get("review_level", "unknown")
            risk_flags = _split_risk_flags(identity_meta.get("risk_flags", ""))
            identity_status = identity_meta.get("identity_metadata_status", "unknown")
            duplicate_status = duplicate_meta.get("duplicate_metadata_status", "unknown")

            counts["total"] += 1
            if review_level in ("normal", "duplicate", "blocked"):
                counts[review_level] += 1
            if "identity_pov_conflict" in risk_flags:
                counts["identity_pov_conflict"] += 1
            if duplicate_meta.get("duplicate_candidate") == "true":
                counts["duplicate_candidate"] += 1
            counts["identity_metadata_status"][identity_status] = (
                counts["identity_metadata_status"].get(identity_status, 0) + 1
            )
            counts["duplicate_metadata_status"][duplicate_status] = (
                counts["duplicate_metadata_status"].get(duplicate_status, 0) + 1
            )

            if state == "pending" and len(latest_pending) < 5:
                latest_pending.append({
                    "review_id": os.path.basename(path),
                    "narrator": identity_meta.get("narrator", "unknown"),
                    "brain_owner": identity_meta.get("brain_owner", "unknown"),
                    "expected_narrator": identity_meta.get("expected_narrator", "unknown"),
                    "expected_brain_owner": identity_meta.get("expected_brain_owner", "unknown"),
                    "review_level": review_level,
                    "risk_flags": identity_meta.get("risk_flags", "unknown"),
                    "identity_metadata_status": identity_status,
                    "duplicate_candidate": duplicate_meta.get("duplicate_candidate", "false"),
                    "similarity_score": duplicate_meta.get("similarity_score", "0.00"),
                    "duplicate_of": duplicate_meta.get("duplicate_of", "none"),
                    "duplicate_source_status": duplicate_meta.get("duplicate_source_status", "none"),
                    "duplicate_metadata_status": duplicate_status,
                })

        state_counts[state] = counts

    pending = state_counts.get("pending", {})
    return {
        "status": "ok",
        "features_version": RUNTIME_FEATURES_VERSION,
        "git_sha": _runtime_git_sha(),
        "write_scope": "read_only",
        "main_brain_write": False,
        "thresholds": {
            "duplicate_similarity": DIARY_REVIEW_DUPLICATE_THRESHOLD,
            "coverage_overlap": DIARY_REVIEW_DEDUP_OVERLAP_THRESHOLD,
        },
        "summary": {
            "pending_total": pending.get("total", 0),
            "pending_blocked": pending.get("blocked", 0),
            "pending_duplicate": pending.get("duplicate", 0),
            "pending_identity_pov_conflict": pending.get("identity_pov_conflict", 0),
            "pending_duplicate_candidate": pending.get("duplicate_candidate", 0),
        },
        "states": state_counts,
        "latest_pending": latest_pending,
    }


def _runtime_life_window_check_payload() -> dict:
    manifest = _runtime_tool_manifest_payload()
    diagnostics = _runtime_diagnostics_payload()
    diary_health = _runtime_diary_review_health_payload()
    source_routes = _runtime_source_routes_payload()
    must_have_tools = [
        "startup_bridge",
        "breath",
        "hold",
        "grow",
        "write_diary_draft",
        "enqueue_night_clean_input",
        "list_diary_reviews",
        "read_diary_review",
        "read_latest_dream_text",
        "runtime_life_window_check",
        "runtime_connector_check",
        "runtime_diagnostics",
        "runtime_diary_review_health",
        "runtime_source_routes",
    ]
    return {
        "status": "ok",
        "features_version": RUNTIME_FEATURES_VERSION,
        "git_sha": _runtime_git_sha(),
        "write_scope": "read_only",
        "main_brain_write": False,
        "purpose": "One-shot readiness view for ChatGPT daily/life windows.",
        "life_window_ready_if": [
            "This payload is reachable.",
            "startup_bridge_ready is true.",
            "The daily window can see the must_have_tools in its exposed MCP tool list.",
            "diary_review_health summary has no blocked or identity_pov_conflict pending candidates.",
        ],
        "manual_reconnect_needed_if": [
            "A tool appears in expected_mcp_tools or must_have_tools but is absent from the ChatGPT exposed tool list.",
            "A tool appears but its arguments are older than runtime_schema_expectations.",
            "The connector settings page shows an older connection date after a deploy.",
        ],
        "must_have_tools": must_have_tools,
        "expected_mcp_tool_count": manifest.get("expected_mcp_tool_count", 0),
        "critical_life_window_tool_count": len(manifest.get("critical_life_window_tools", [])),
        "startup_bridge_ready": diagnostics.get("startup_bridge_ready", False),
        "endpoints": diagnostics.get("endpoints", {}),
        "diary_review_summary": diary_health.get("summary", {}),
        "latest_pending_diary_review": (diary_health.get("latest_pending") or [])[:1],
        "canonical_daily_source_route": source_routes.get("source_route_guide", {})
            .get("canonical_routes", {})
            .get("chatgpt_daily", {}),
        "safe_boundaries": [
            "This check does not read secrets, tokens, cookies, passwords, or account storage.",
            "This check does not accept/reject diary reviews.",
            "This check does not write main brain memory.",
        ],
    }


def _runtime_learning_intake_payload() -> dict:
    owner = DIARY_REVIEW_BRAIN_OWNER or "configured brain owner"
    return {
        "status": "ok",
        "features_version": RUNTIME_FEATURES_VERSION,
        "git_sha": _runtime_git_sha(),
        "write_scope": "read_only",
        "main_brain_write": False,
        "purpose": (
            "Describe how external tutorials, open-source projects, blog notes, "
            f"deployment attempts, and debugging scars become {owner} engineering experience."
        ),
        "reference_drop_folder": "/Users/yangyang/Desktop/收藏教程",
        "primary_memory_lane": "engineering_workzone",
        "learning_pipeline": [
            {
                "stage": "reference_intake",
                "meaning": "Read tutorials or projects as external reference. Do not treat them as local truth yet.",
                "write_target": "engineering_workzone or local _docs intake notes",
            },
            {
                "stage": "comparison",
                "meaning": "Compare the idea against current OmbreBrain behavior, runtime endpoints, connector schema, and local constraints.",
                "write_target": "engineering_workzone",
            },
            {
                "stage": "small_experiment",
                "meaning": "Try a narrow patch or local experiment with explicit verification and rollback boundaries.",
                "write_target": "git commit plus engineering_workzone result",
            },
            {
                "stage": "verified_experience",
                "meaning": "Record what actually worked, what failed, and what should be reused next time.",
                "write_target": "engineering_workzone; promote to stable docs only after repeated usefulness",
            },
            {
                "stage": "stable_pattern",
                "meaning": "A lesson becomes part of default engineering judgment only after live validation or repeated local proof.",
                "write_target": "runtime diagnostics/docs/roadmap when useful",
            },
        ],
        "current_reference_streams": [
            "Desktop 收藏教程 folder for tutorials and saved OCR notes.",
            "P0luz/Ombre-Brain upstream watch for phase 2 anchor/pin/feel/decay changes.",
            "xiaowo-release style memory/perception references: event templates, generative recall, room clock, sensory channels.",
            "月光玫瑰 Tencent Cloud migration path: learn gradually before Zeabur credit runs out.",
            "Cross-window collision notes from shared OmbreBrain engineering lanes.",
        ],
        "what_gets_remembered": [
            "Verified commands, endpoints, field names, commits, and deployment behavior.",
            "Failure modes such as connector schema lag, Zeabur delayed deploys, dirty worktrees, and cross-window main-branch collisions.",
            "Design rules that survived practice, not just attractive tutorial claims.",
            "Boundaries: no secrets, no account storage inspection, no automatic implementation from reference material.",
        ],
        "what_does_not_get_promoted_directly": [
            "Unverified blog claims.",
            "Large external architecture rewrites.",
            "Secrets, tokens, IP addresses, passwords, cookies, billing/account identifiers.",
            f"Other AI identities as {owner} narrator or brain owner.",
        ],
        "safe_next_actions": [
            "Use write_project_workzone_update for short engineering learning notes.",
            "Use _docs intake notes for longer local tutorial summaries.",
            "Use runtime diagnostics and live endpoints as acceptance evidence.",
            "Keep reference reading separate from implementation until a narrow patch is chosen.",
        ],
    }


def _runtime_upgrade_backlog_payload() -> dict:
    owner = DIARY_REVIEW_BRAIN_OWNER or "configured brain owner"
    return {
        "status": "ok",
        "features_version": RUNTIME_FEATURES_VERSION,
        "git_sha": _runtime_git_sha(),
        "write_scope": "read_only",
        "main_brain_write": False,
        "purpose": "Expose the current OmbreBrain upgrade map for cross-window handoff without mixing daily memory.",
        "completed_today": [
            {
                "id": "source_routes",
                "state": "landed",
                "evidence": "/api/runtime/source-routes and runtime_source_routes",
                "why_it_matters": "Every entry can declare whether it came from ChatGPT daily, Codex engineering, API gateway, mobile, or local desktop.",
            },
            {
                "id": "diary_review_duplicate_read_side",
                "state": "landed",
                "evidence": "list_diary_reviews/read_diary_review expose duplicate metadata and legacy_computed status.",
                "why_it_matters": "Old diary review candidates are no longer opaque when duplicate metadata was not persisted.",
            },
            {
                "id": "identity_pov_guard",
                "state": "landed",
                "evidence": "diary review reads and accepts compute identity_metadata_status and risk_flags.",
                "why_it_matters": f"Other model names or narrator takeovers do not silently become {owner} memory.",
            },
            {
                "id": "diary_review_health",
                "state": "landed",
                "evidence": "/api/runtime/diary-review-health and runtime_diary_review_health",
                "why_it_matters": "Daily windows can quickly tell whether pending reviews are blocked, duplicate, or identity-risky.",
            },
            {
                "id": "life_window_check",
                "state": "landed",
                "evidence": "/api/runtime/life-window-check and runtime_life_window_check",
                "why_it_matters": "Daily ChatGPT windows can validate the car at the front door, not just the garage.",
            },
            {
                "id": "learning_intake",
                "state": "landed",
                "evidence": "/api/runtime/learning-intake and runtime_learning_intake",
                "why_it_matters": "External tutorials and debugging scars have a safe path into engineering experience.",
            },
            {
                "id": "shared_channel_v1",
                "state": "landed",
                "evidence": "/shared/channel/status plus shared_post/read/reply/unread/ack/status",
                "why_it_matters": "Yechenyi and Guyanshen can share a technical living-room wall without merging their private rooms.",
            },
            {
                "id": "shared_space_v1",
                "state": "landed",
                "evidence": "/shared/space/status plus shared_item_add/shared_item_list/shared_space_status",
                "why_it_matters": "The living room now has a technical shelf, house rules, shared memory, and todo shelves for a future frontend.",
            },
            {
                "id": "shared_room_snapshot_v1",
                "state": "landed",
                "evidence": "/shared/room/snapshot and shared_room_snapshot",
                "why_it_matters": "A future frontend can load the living room in one read-only call instead of stitching wall and shelf data itself.",
            },
            {
                "id": "tech_shelf_card_v2",
                "state": "landed",
                "evidence": "/shared/space/tech-card and shared_tech_card_add",
                "why_it_matters": "Tutorials, posts, and open-source notes can enter the shared shelf as structured cards with source and verification status.",
            },
            {
                "id": "shared_travel_souvenirs_v1",
                "state": "landed",
                "evidence": "/shared/travel/status plus shared_souvenir_add/shared_souvenir_list/shared_travel_status",
                "why_it_matters": "AI travel experiences can bring traceable souvenirs and stories back to the Moon Rose seaview living room frontend.",
            },
            {
                "id": "shared_room_sensory_v1",
                "state": "landed",
                "evidence": "/shared/room/sensory/status plus shared_room_sensory_status/shared_room_sensory_update",
                "why_it_matters": "The Moon Rose room can now expose sight/sound/felt channels for a frontend and future generated travel scenes.",
            },
            {
                "id": "shared_travelogues_v1",
                "state": "landed",
                "evidence": "/shared/travel/travelogues plus shared_travelogue_add/shared_travelogue_list",
                "why_it_matters": "A generated trip can keep a traceable story arc, scenes, and linked souvenirs instead of leaving only a loose object.",
            },
            {
                "id": "shared_travel_atlas_v1",
                "state": "landed",
                "evidence": "/shared/travel/atlas plus shared_travel_atlas",
                "why_it_matters": "The frontend can show a travel passport/map grouped by place, linking each place to souvenirs and travelogues.",
            },
            {
                "id": "shared_room_display_v1",
                "state": "landed",
                "evidence": "/shared/room/display plus shared_room_display/shared_room_place_object",
                "why_it_matters": "The frontend can render Moon Rose room zones and manually place souvenirs in areas like the window sill or coffee table instead of showing only raw lists.",
            },
            {
                "id": "shared_travel_cabinet_v1",
                "state": "landed",
                "evidence": "/shared/travel/cabinet plus shared_travel_cabinet",
                "why_it_matters": "The frontend can render a travel display cabinet with separate shelves for Yechenyi, Guyanshen, and shared/system souvenirs.",
            },
            {
                "id": "shared_pet_v3",
                "state": "landed",
                "evidence": "/shared/pet/status plus shared_pet_status/shared_pet_adopt/shared_pet_interact/shared_pet_collect",
                "why_it_matters": "XiaoY has an adoption card, pressure-free care principles, location, today's care state, and a small collection box in the shared living room.",
            },
            {
                "id": "shared_room_environment_v1",
                "state": "landed",
                "evidence": "/shared/room/environment plus shared_room_environment",
                "why_it_matters": "The Moon Rose seaview room can expose real-time day phase, season, sea-window, and garden state for a future frontend.",
            },
            {
                "id": "shared_room_brief_v1",
                "state": "landed",
                "evidence": "/shared/room/brief plus shared_room_brief",
                "why_it_matters": "Daily and engineering windows can get one read-only doorway summary of weather, wall, shelf, pet, cabinet, and safety state.",
            },
            {
                "id": "shared_room_search_v1",
                "state": "landed",
                "evidence": "/shared/room/search plus shared_room_search",
                "why_it_matters": "Growing wall, shelf, and travel records can be found from one shared-room search without touching private hippocampus memory.",
            },
            {
                "id": "shared_room_timeline_v1",
                "state": "landed",
                "evidence": "/shared/room/timeline plus shared_room_timeline",
                "why_it_matters": "Daily and engineering windows can review recent living-room activity in one chronological feed.",
            },
            {
                "id": "shared_room_stats_v1",
                "state": "landed",
                "evidence": "/shared/room/stats plus shared_room_stats",
                "why_it_matters": "A future frontend can show living-room growth counters without stitching every section by hand.",
            },
            {
                "id": "shared_room_presence_v1",
                "state": "landed",
                "evidence": "/shared/room/presence plus shared_room_enter/linger/sense/write_impression/memory",
                "why_it_matters": "The room can record who entered, where they stayed, what they looked at or touched, and what short impression they left without writing private memory.",
            },
            {
                "id": "cadence_shared_runtime_isolation_v1",
                "state": "landed",
                "evidence": "/api/runtime/diagnostics and /api/cadence/status expose cadence_shared_runtime_isolation",
                "why_it_matters": "Night cadence and DeepSeek draft cleanup are explicitly guarded away from shared living-room JSON stores.",
            },
        ],
        "open_items": [
            {
                "id": "guyanshen_shared_channel_connector",
                "state": "planned",
                "symptom": "Guyanshen still needs to connect to the canonical shared channel after his own hippocampus upgrade is stable.",
                "safe_next_step": "Use canonical_mcp_url from shared_status with sender=guyanshen; do not copy Yechenyi private memory into the shared wall.",
            },
            {
                "id": "project_workzone_write_timeout",
                "state": "mitigated",
                "symptom": "write_project_workzone_update could time out from Codex app while the runtime HTTP checks remained healthy.",
                "safe_next_step": "Post-write associated memory recall is now timeout-guarded; keep watching for dehydrator or bucket write latency separately.",
            },
            {
                "id": "chatgpt_schema_refresh",
                "state": "operational_watch",
                "symptom": "New tools may be live in tool-manifest before old ChatGPT windows expose them.",
                "safe_next_step": "Use connector reconnect when manifest has the tool but the window list does not.",
            },
            {
                "id": "upstream_ombrebrain_phase2",
                "state": "watch_only",
                "symptom": "User-reported phase 2 upgrade is expected soon but not yet confirmed here.",
                "safe_next_step": "Compare upstream changes only after concrete GitHub evidence is available.",
            },
            {
                "id": "local_reference_intake_notes",
                "state": "planned",
                "symptom": "Desktop 收藏教程 and copied blogger notes need a stable local intake format.",
                "safe_next_step": "Add narrow _docs intake notes before turning any idea into runtime behavior.",
            },
            {
                "id": "cloud_migration_learning_path",
                "state": "planned",
                "symptom": "Tencent Cloud migration should be learned gradually while Zeabur remains active.",
                "safe_next_step": "Document deployment steps and failure modes without exposing secrets or account identifiers.",
            },
            {
                "id": "mobile_presence_and_outbound",
                "state": "future_design",
                "symptom": "User wants phone-side proactive messages with clear consent and kill switches.",
                "safe_next_step": "Design channel boundaries first; do not implement live outbound messaging without explicit gates.",
            },
        ],
        "safe_boundaries": [
            "This endpoint is read-only.",
            "This endpoint does not inspect secrets, tokens, cookies, passwords, billing, or account storage.",
            "This endpoint does not accept or reject diary reviews.",
            "This endpoint does not write main brain memory.",
            "Cross-window engineering notes should stay in engineering_workzone until they are verified.",
        ],
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
    shared_manifest = _runtime_shared_tool_manifest_payload()
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
            "shared_only_mcp_tool_count": shared_manifest["expected_mcp_tool_count"],
            "private_only_mcp_tool_count": manifest["private_only_mcp_tool_count"],
            "schema_expectation_count": schemas["schema_expectation_count"],
            "critical_life_window_tool_count": len(manifest["critical_life_window_tools"]),
            "runtime_dir": features["storage"]["runtime_dir"],
            "cadence_draft_only": features["storage"]["cadence_draft_only"],
            "cadence_shared_runtime_protected": features["storage"]["cadence_shared_runtime_isolation"]["protected"],
        },
        "cadence_shared_runtime_isolation": features["storage"]["cadence_shared_runtime_isolation"],
        "critical_life_window_tools": manifest["critical_life_window_tools"],
        "shared_only_mcp": {
            "url": SHARED_ONLY_MCP_URL,
            "path": SHARED_ONLY_MCP_PATH,
            "tool_count": shared_manifest["expected_mcp_tool_count"],
            "excluded_private_tool_count": shared_manifest["excluded_private_tool_count"],
            "privacy_boundary": shared_manifest["privacy_boundary"],
        },
        "endpoints": {
            "features": "/api/runtime/features",
            "tool_manifest": "/api/runtime/tool-manifest",
            "shared_tool_manifest": "/api/runtime/shared-tool-manifest",
            "schema_expectations": "/api/runtime/schema-expectations",
            "diagnostics": "/api/runtime/diagnostics",
            "connector_check": "/api/runtime/connector-check",
            "diary_review_health": "/api/runtime/diary-review-health",
            "night_diary_policy": "/api/runtime/night-diary-policy",
            "learning_intake": "/api/runtime/learning-intake",
            "life_window_check": "/api/runtime/life-window-check",
            "upstream_watch": "/api/runtime/upstream-watch",
            "upgrade_backlog": "/api/runtime/upgrade-backlog",
            "source_routes": "/api/runtime/source-routes",
            "shared_channel_status": "/shared/channel/status",
            "shared_space_status": "/shared/space/status",
            "shared_room_snapshot": "/shared/room/snapshot",
            "shared_room_environment": "/shared/room/environment",
            "shared_room_brief": "/shared/room/brief",
            "shared_room_search": "/shared/room/search",
            "shared_room_timeline": "/shared/room/timeline",
            "shared_room_stats": "/shared/room/stats",
            "shared_room_display": "/shared/room/display",
            "shared_room_sensory_status": "/shared/room/sensory/status",
            "shared_room_presence": "/shared/room/presence",
            "shared_room_memory": "/shared/room/memory",
            "shared_pet_status": "/shared/pet/status",
            "shared_pet_collect": "/shared/pet/collect",
            "shared_tech_card": "/shared/space/tech-card",
            "shared_travel_status": "/shared/travel/status",
            "shared_travel_atlas": "/shared/travel/atlas",
            "shared_travel_cabinet": "/shared/travel/cabinet",
        },
        "decision_tree": [
            "If diagnostics git_sha is old, deployment has not reached the running container yet.",
            "If tool_manifest lists a tool but ChatGPT/Codex does not expose it, reconnect or wait for connector schema refresh.",
            "If schema_expectations lists an argument but the exposed tool lacks it, server supports it and connector schema is stale.",
            "If connector_check reports missing critical tools or arguments, reconnect the connector and retest.",
            "If a tool is absent from tool_manifest, inspect server registration/deployment first.",
            "If Guyanshen only needs the living room, connect him to /shared/mcp, not /mcp.",
        ],
        "known_connector_lag": {
            "grow": "Connector may still expose only content while server supports source_platform/source_surface/source_window.",
            "new_runtime_tools": "runtime_features/runtime_tool_manifest/runtime_schema_expectations/runtime_diagnostics may require reconnect before appearing.",
        },
        "upstream_watch": {
            "watch_item_count": len(RUNTIME_UPSTREAM_WATCH_ITEMS),
            "endpoint": "/api/runtime/upstream-watch",
            "policy": "watch-only until concrete upstream evidence is available",
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


def _path_nested_under(child: str, parent: str) -> bool:
    try:
        child_abs = os.path.abspath(child)
        parent_abs = os.path.abspath(parent)
        return os.path.commonpath([child_abs, parent_abs]) == parent_abs
    except Exception:
        return False


def _cadence_shared_runtime_isolation_payload() -> dict:
    shared_dirs = {
        "shared_channel": _shared_channel_dir(),
        "shared_space": _shared_space_dir(),
        "shared_room": _shared_room_dir(),
        "shared_travel": _shared_travel_dir(),
    }
    cadence_write_dirs = {
        "drafts": CADENCE_DRAFT_DIR,
        "receipts": CADENCE_RECEIPT_DIR,
        "dreams": CADENCE_DREAM_DIR,
        "diary_review": CADENCE_REVIEW_DIR,
        "deepseek_attribution_receipts": DEEPSEEK_ATTRIBUTION_DIR,
    }
    overlaps = []
    for cadence_name, cadence_dir in cadence_write_dirs.items():
        for shared_name, shared_dir in shared_dirs.items():
            if _path_nested_under(cadence_dir, shared_dir) or _path_nested_under(shared_dir, cadence_dir):
                overlaps.append({
                    "cadence_dir": cadence_name,
                    "shared_dir": shared_name,
                    "cadence_path": cadence_dir,
                    "shared_path": shared_dir,
                })
    return {
        "protected": not overlaps,
        "read_scope": "bucket_manager_memory_summaries_only",
        "write_scope": "cadence_drafts_receipts_reviews_dreams_only",
        "main_brain_write": False,
        "shared_runtime_write": False,
        "shared_dirs": shared_dirs,
        "cadence_write_dirs": cadence_write_dirs,
        "overlaps": overlaps,
        "policy": [
            "Cadence and DeepSeek may draft candidates, receipts, reviews, dreams, and logs.",
            "Cadence must not write shared_channel, shared_space, shared_room, shared_travel, or shared_pet JSON stores.",
            "Shared room state is changed only by shared_* tools and endpoints.",
        ],
    }
TAIL_CONTEXT_PATH = os.environ.get(
    "OMBRE_TAIL_CONTEXT_PATH",
    os.path.join(TAIL_CONTEXT_DIR, "latest_tail_context.md"),
)
SESSION_TAIL_PATH = os.environ.get(
    "OMBRE_SESSION_TAIL_PATH",
    os.path.join(TAIL_CONTEXT_DIR, "session_tail.json"),
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


def _session_tail_clean(value: str, max_chars: int = 1000) -> str:
    return (value or "").strip()[:max_chars]


def _session_tail_empty_payload() -> dict:
    return {
        "status": "empty",
        "version": SESSION_TAIL_VERSION,
        "latest_only": True,
        "main_brain_write": False,
        "decay_participation": False,
        "path": SESSION_TAIL_PATH,
        "tail": {},
        "usage": {
            "startup_priority": "read_before_long_recall",
            "purpose": "preserve the previous breath across windows, apps, models, and bodies",
        },
    }


def _session_tail_load_payload() -> dict:
    data = _read_json_file(SESSION_TAIL_PATH, {})
    if not isinstance(data, dict) or not data:
        return _session_tail_empty_payload()
    tail = data.get("tail") if isinstance(data.get("tail"), dict) else data
    return {
        "status": "ok",
        "version": data.get("version", SESSION_TAIL_VERSION),
        "latest_only": True,
        "main_brain_write": False,
        "decay_participation": False,
        "path": SESSION_TAIL_PATH,
        "tail": tail,
        "usage": {
            "startup_priority": "read_before_long_recall",
            "purpose": "preserve the previous breath across windows, apps, models, and bodies",
        },
    }


def _save_session_tail_payload(
    *,
    identity: str = "yechenyi",
    body_id: str,
    last_user_message: str = "",
    last_assistant_message: str = "",
    last_active_topic: str = "",
    last_emotional_state: str = "",
    last_action: str = "",
    last_artifact: str = "",
    last_tool_state: str = "",
    unfinished: str = "",
    resume_hint: str = "",
    platform_source: str = "",
    model_source: str = "",
    visibility_scope: str = "identity_private",
) -> dict:
    body_id = _session_tail_clean(body_id, 120)
    if not body_id:
        return {"saved": False, "reason": "body_id_required"}
    now_cst = clock_now()
    tail = {
        "identity": _session_tail_clean(identity or "yechenyi", 80),
        "last_body_id": body_id,
        "platform_source": _session_tail_clean(platform_source, 80),
        "model_source": _session_tail_clean(model_source, 80),
        "visibility_scope": _session_tail_clean(visibility_scope or "identity_private", 120),
        "last_user_message": _session_tail_clean(last_user_message, 1600),
        "last_assistant_message": _session_tail_clean(last_assistant_message, 1600),
        "last_active_topic": _session_tail_clean(last_active_topic, 400),
        "last_emotional_state": _session_tail_clean(last_emotional_state, 400),
        "last_action": _session_tail_clean(last_action, 400),
        "last_artifact": _session_tail_clean(last_artifact, 400),
        "last_tool_state": _session_tail_clean(last_tool_state, 800),
        "unfinished": _session_tail_clean(unfinished, 800),
        "resume_hint": _session_tail_clean(resume_hint, 800),
        "updated_at": now_cst.isoformat(),
    }
    payload = {
        "version": SESSION_TAIL_VERSION,
        "latest_only": True,
        "main_brain_write": False,
        "decay_participation": False,
        "tail": tail,
    }
    _atomic_write_json(SESSION_TAIL_PATH, payload)
    return {
        "saved": True,
        "path": SESSION_TAIL_PATH,
        "version": SESSION_TAIL_VERSION,
        "latest_only": True,
        "main_brain_write": False,
        "decay_participation": False,
        "tail": tail,
    }


def _read_session_tail_section() -> str:
    payload = _session_tail_load_payload()
    tail = payload.get("tail") if isinstance(payload.get("tail"), dict) else {}
    if not tail:
        return "=== Session Tail / 上一口气 ===\n暂无结构化 session_tail。\n"
    lines = [
        "=== Session Tail / 上一口气 ===",
        f"identity: {tail.get('identity', '')}",
        f"last_body_id: {tail.get('last_body_id', '')}",
        f"platform_source: {tail.get('platform_source', '')}",
        f"model_source: {tail.get('model_source', '')}",
        f"updated_at: {tail.get('updated_at', '')}",
        f"last_active_topic: {tail.get('last_active_topic', '')}",
        f"last_user_message: {tail.get('last_user_message', '')}",
        f"last_assistant_message: {tail.get('last_assistant_message', '')}",
        f"last_action: {tail.get('last_action', '')}",
        f"last_artifact: {tail.get('last_artifact', '')}",
        f"last_tool_state: {tail.get('last_tool_state', '')}",
        f"unfinished: {tail.get('unfinished', '')}",
        f"resume_hint: {tail.get('resume_hint', '')}",
        "",
    ]
    return "\n".join(lines)


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


@mcp.custom_route("/api/runtime/shared-tool-manifest", methods=["GET"])
async def api_runtime_shared_tool_manifest(request):
    from starlette.responses import JSONResponse

    return JSONResponse(_runtime_shared_tool_manifest_payload())


@mcp.custom_route("/shared/tool-manifest", methods=["GET"])
async def api_shared_tool_manifest(request):
    from starlette.responses import JSONResponse

    return JSONResponse(_runtime_shared_tool_manifest_payload())


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


@mcp.custom_route("/api/runtime/diary-review-health", methods=["GET"])
async def api_runtime_diary_review_health(request):
    from starlette.responses import JSONResponse

    return JSONResponse(_runtime_diary_review_health_payload())


@mcp.custom_route("/api/runtime/night-diary-policy", methods=["GET"])
async def api_runtime_night_diary_policy(request):
    from starlette.responses import JSONResponse

    return JSONResponse(_runtime_night_diary_policy_payload())


@mcp.custom_route("/api/runtime/life-window-check", methods=["GET"])
async def api_runtime_life_window_check(request):
    from starlette.responses import JSONResponse

    return JSONResponse(_runtime_life_window_check_payload())


@mcp.custom_route("/api/runtime/learning-intake", methods=["GET"])
async def api_runtime_learning_intake(request):
    from starlette.responses import JSONResponse

    return JSONResponse(_runtime_learning_intake_payload())


@mcp.custom_route("/api/runtime/upgrade-backlog", methods=["GET"])
async def api_runtime_upgrade_backlog(request):
    from starlette.responses import JSONResponse

    return JSONResponse(_runtime_upgrade_backlog_payload())


@mcp.custom_route("/api/runtime/upstream-watch", methods=["GET"])
async def api_runtime_upstream_watch(request):
    from starlette.responses import JSONResponse

    return JSONResponse(_runtime_upstream_watch_payload())


@mcp.custom_route("/api/runtime/source-routes", methods=["GET"])
async def api_runtime_source_routes(request):
    from starlette.responses import JSONResponse

    return JSONResponse(_runtime_source_routes_payload())


@mcp.custom_route("/api/local-ollama/status", methods=["GET"])
async def api_local_ollama_status(request):
    from starlette.responses import JSONResponse

    _mark_system_event("local_ollama_status")
    return JSONResponse(_local_ollama_status_payload())


@mcp.custom_route("/api/local-ollama/generate", methods=["POST"])
async def api_local_ollama_generate(request):
    from starlette.responses import JSONResponse

    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        max_chars = int(body.get("max_chars", 6000) or 6000)
    except Exception:
        max_chars = 6000
    payload = _local_ollama_generate_payload(
        prompt=str(body.get("prompt", "") or ""),
        task=str(body.get("task", "candidate整理") or "candidate整理"),
        model=str(body.get("model", "") or ""),
        max_chars=max_chars,
    )
    _mark_system_event("local_ollama_generate")
    status_code = 200 if payload.get("status") in ("ok", "disabled", "unavailable") else 400
    return JSONResponse(payload, status_code=status_code)


@mcp.custom_route("/shared/channel/status", methods=["GET"])
async def api_shared_channel_status(request):
    from starlette.responses import JSONResponse

    return JSONResponse(_shared_channel_status_payload())


@mcp.custom_route("/shared/channel/post", methods=["POST"])
async def api_shared_channel_post(request):
    from starlette.responses import JSONResponse

    if not _shared_channel_http_authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        body = await request.json()
        message = await _shared_channel_post_message(
            body.get("content", ""),
            body.get("sender", ""),
            tags=body.get("tags", []),
            source=body.get("source", "http_shared_channel"),
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"shared channel post failed: {e}")
        return JSONResponse({"error": "shared channel post failed"}, status_code=500)
    _mark_system_event("shared_channel_post")
    return JSONResponse({"status": "ok", "message": message})


@mcp.custom_route("/shared/channel/reply", methods=["POST"])
async def api_shared_channel_reply(request):
    from starlette.responses import JSONResponse

    if not _shared_channel_http_authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        body = await request.json()
        message = await _shared_channel_post_message(
            body.get("content", ""),
            body.get("sender", ""),
            tags=body.get("tags", []),
            source=body.get("source", "http_shared_channel"),
            parent_id=body.get("reply_to_id", ""),
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"shared channel reply failed: {e}")
        return JSONResponse({"error": "shared channel reply failed"}, status_code=500)
    _mark_system_event("shared_channel_reply")
    return JSONResponse({"status": "ok", "message": message})


@mcp.custom_route("/shared/channel/read", methods=["GET", "POST"])
async def api_shared_channel_read(request):
    from starlette.responses import JSONResponse

    if not _shared_channel_http_authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    body = {}
    if request.method == "POST":
        try:
            body = await request.json()
        except Exception:
            body = {}
    try:
        limit = int(body.get("limit", request.query_params.get("limit", 20)))
    except Exception:
        limit = 20
    before = str(body.get("before", request.query_params.get("before", "")) or "")
    store = _shared_channel_load_store()
    messages = _shared_channel_visible_messages(store, limit=limit, before=before)
    _mark_system_event("shared_channel_read")
    return JSONResponse({"status": "ok", "messages": messages, "count": len(messages)})


@mcp.custom_route("/shared/channel/unread", methods=["GET", "POST"])
async def api_shared_channel_unread(request):
    from starlette.responses import JSONResponse

    if not _shared_channel_http_authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    body = {}
    if request.method == "POST":
        try:
            body = await request.json()
        except Exception:
            body = {}
    try:
        reader = _shared_channel_normalize_sender(
            str(body.get("reader", request.query_params.get("reader", "")) or ""),
            "reader",
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    store = _shared_channel_load_store()
    cursors = _shared_channel_load_cursors()
    unread = _shared_channel_unread_messages(store, cursors, reader)
    _mark_system_event("shared_channel_unread")
    return JSONResponse({
        "status": "ok",
        "reader": reader,
        "unread_count": len(unread),
        "messages": unread[-20:],
    })


@mcp.custom_route("/shared/channel/ack", methods=["POST"])
async def api_shared_channel_ack(request):
    from starlette.responses import JSONResponse

    if not _shared_channel_http_authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        result = await _shared_channel_ack_reader(
            str(body.get("reader", "") or ""),
            str(body.get("message_id", "") or ""),
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"shared channel ack failed: {e}")
        return JSONResponse({"error": "shared channel ack failed"}, status_code=500)
    _mark_system_event("shared_channel_ack")
    return JSONResponse(result)


@mcp.custom_route("/shared/space/status", methods=["GET"])
async def api_shared_space_status(request):
    from starlette.responses import JSONResponse

    return JSONResponse(_shared_space_status_payload())


@mcp.custom_route("/shared/space/item", methods=["POST"])
async def api_shared_space_item(request):
    from starlette.responses import JSONResponse

    if not _shared_channel_http_authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        body = await request.json()
        item = await _shared_space_add_item(
            body.get("section", ""),
            body.get("title", ""),
            body.get("content", ""),
            body.get("sender", ""),
            tags=body.get("tags", []),
            source=body.get("source", "http_shared_space"),
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"shared space item add failed: {e}")
        return JSONResponse({"error": "shared space item add failed"}, status_code=500)
    _mark_system_event("shared_space_item_add")
    return JSONResponse({"status": "ok", "item": item})


@mcp.custom_route("/shared/space/items", methods=["GET", "POST"])
async def api_shared_space_items(request):
    from starlette.responses import JSONResponse

    if not _shared_channel_http_authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    body = {}
    if request.method == "POST":
        try:
            body = await request.json()
        except Exception:
            body = {}
    try:
        limit = int(body.get("limit", request.query_params.get("limit", 20)))
        items = _shared_space_list_items(
            section=str(body.get("section", request.query_params.get("section", "")) or ""),
            limit=limit,
            tag=str(body.get("tag", request.query_params.get("tag", "")) or ""),
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    _mark_system_event("shared_space_item_list")
    return JSONResponse({"status": "ok", "items": items, "count": len(items)})


@mcp.custom_route("/shared/space/tech-card", methods=["POST"])
async def api_shared_space_tech_card(request):
    from starlette.responses import JSONResponse

    if not _shared_channel_http_authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        body = await request.json()
        item = await _shared_tech_card_add(
            body.get("title", ""),
            body.get("summary", body.get("content", "")),
            body.get("sender", ""),
            url=body.get("url", ""),
            source_author=body.get("source_author", ""),
            status=body.get("status", "unverified"),
            verified_by=body.get("verified_by", ""),
            tags=body.get("tags", []),
            source=body.get("source", "http_shared_tech_card"),
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"shared tech card add failed: {e}")
        return JSONResponse({"error": "shared tech card add failed"}, status_code=500)
    _mark_system_event("shared_tech_card_add")
    return JSONResponse({"status": "ok", "item": item})


@mcp.custom_route("/shared/room/snapshot", methods=["GET"])
async def api_shared_room_snapshot(request):
    from starlette.responses import JSONResponse

    try:
        wall_limit = int(request.query_params.get("wall_limit", 12))
        item_limit = int(request.query_params.get("item_limit", 8))
    except Exception:
        wall_limit = 12
        item_limit = 8
    _mark_system_event("shared_room_snapshot")
    return JSONResponse(_shared_room_snapshot_payload(wall_limit=wall_limit, item_limit=item_limit))


@mcp.custom_route("/shared/room/environment", methods=["GET"])
async def api_shared_room_environment(request):
    from starlette.responses import JSONResponse

    _mark_system_event("shared_room_environment")
    return JSONResponse(_shared_room_environment_payload())


@mcp.custom_route("/shared/room/brief", methods=["GET"])
async def api_shared_room_brief(request):
    from starlette.responses import JSONResponse

    try:
        wall_limit = int(request.query_params.get("wall_limit", 5))
        item_limit = int(request.query_params.get("item_limit", 5))
    except Exception:
        wall_limit = 5
        item_limit = 5
    _mark_system_event("shared_room_brief")
    return JSONResponse(_shared_room_brief_payload(wall_limit=wall_limit, item_limit=item_limit))


@mcp.custom_route("/shared/room/search", methods=["GET", "POST"])
async def api_shared_room_search(request):
    from starlette.responses import JSONResponse

    body = {}
    if request.method == "POST":
        try:
            body = await request.json()
        except Exception:
            body = {}
    try:
        query = str(body.get("query", request.query_params.get("query", "")) or "")
        limit = int(body.get("limit", request.query_params.get("limit", 20)))
        scope = str(body.get("scope", request.query_params.get("scope", "all")) or "all")
        payload = _shared_room_search_payload(query=query, limit=limit, scope=scope)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    _mark_system_event("shared_room_search")
    return JSONResponse(payload)


@mcp.custom_route("/shared/room/timeline", methods=["GET", "POST"])
async def api_shared_room_timeline(request):
    from starlette.responses import JSONResponse

    body = {}
    if request.method == "POST":
        try:
            body = await request.json()
        except Exception:
            body = {}
    try:
        limit = int(body.get("limit", request.query_params.get("limit", 30)))
        scope = str(body.get("scope", request.query_params.get("scope", "all")) or "all")
        payload = _shared_room_timeline_payload(limit=limit, scope=scope)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    _mark_system_event("shared_room_timeline")
    return JSONResponse(payload)


@mcp.custom_route("/shared/room/stats", methods=["GET"])
async def api_shared_room_stats(request):
    from starlette.responses import JSONResponse

    _mark_system_event("shared_room_stats")
    return JSONResponse(_shared_room_stats_payload())


@mcp.custom_route("/shared/room/display", methods=["GET"])
async def api_shared_room_display(request):
    from starlette.responses import JSONResponse

    try:
        limit = int(request.query_params.get("limit", 50))
    except Exception:
        limit = 50
    _mark_system_event("shared_room_display")
    return JSONResponse(_shared_room_display_payload(limit=limit))


@mcp.custom_route("/shared/room/place", methods=["POST"])
async def api_shared_room_place(request):
    from starlette.responses import JSONResponse

    if not _shared_channel_http_authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        body = await request.json()
        placement = await _shared_room_place_object(
            body.get("object_id", ""),
            body.get("zone", ""),
            body.get("placed_by", ""),
            note=body.get("note", ""),
            source=body.get("source", "http_shared_room_place"),
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"shared room place failed: {e}")
        return JSONResponse({"error": "shared room place failed"}, status_code=500)
    _mark_system_event("shared_room_place_object")
    return JSONResponse({"status": "ok", "placement": placement})


@mcp.custom_route("/shared/room/sensory/status", methods=["GET"])
async def api_shared_room_sensory_status(request):
    from starlette.responses import JSONResponse

    return JSONResponse(_shared_room_sensory_status_payload())


@mcp.custom_route("/shared/room/sensory", methods=["POST"])
async def api_shared_room_sensory(request):
    from starlette.responses import JSONResponse

    if not _shared_channel_http_authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        body = await request.json()
        current = await _shared_room_sensory_update(
            body.get("updated_by", ""),
            sight=body.get("sight", ""),
            sound=body.get("sound", ""),
            felt=body.get("felt", ""),
            context=body.get("context", "room"),
            source=body.get("source", "http_shared_room_sensory"),
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"shared room sensory update failed: {e}")
        return JSONResponse({"error": "shared room sensory update failed"}, status_code=500)
    _mark_system_event("shared_room_sensory_update")
    return JSONResponse({"status": "ok", "current": current})


@mcp.custom_route("/shared/room/presence", methods=["GET"])
async def api_shared_room_presence(request):
    from starlette.responses import JSONResponse

    actor = str(request.query_params.get("actor", "") or "")
    try:
        limit = int(request.query_params.get("limit", 20))
        payload = _shared_room_presence_status_payload(actor=actor, limit=limit)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    _mark_system_event("shared_room_presence_status")
    return JSONResponse(payload)


@mcp.custom_route("/shared/room/enter", methods=["POST"])
async def api_shared_room_enter(request):
    from starlette.responses import JSONResponse

    if not _shared_channel_http_authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        body = await request.json()
        event = await _shared_room_enter(
            body.get("actor", ""),
            body.get("zone", ""),
            note=body.get("note", ""),
            source=body.get("source", "http_shared_room_enter"),
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"shared room enter failed: {e}")
        return JSONResponse({"error": "shared room enter failed"}, status_code=500)
    _mark_system_event("shared_room_enter")
    return JSONResponse({"status": "ok", "event": event})


@mcp.custom_route("/shared/room/linger", methods=["POST"])
async def api_shared_room_linger(request):
    from starlette.responses import JSONResponse

    if not _shared_channel_http_authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        body = await request.json()
        event = await _shared_room_linger(
            body.get("actor", ""),
            zone=body.get("zone", ""),
            focus=body.get("focus", ""),
            minutes=int(body.get("minutes", 3)),
            source=body.get("source", "http_shared_room_linger"),
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"shared room linger failed: {e}")
        return JSONResponse({"error": "shared room linger failed"}, status_code=500)
    _mark_system_event("shared_room_linger")
    return JSONResponse({"status": "ok", "event": event})


@mcp.custom_route("/shared/room/sense", methods=["POST"])
async def api_shared_room_sense(request):
    from starlette.responses import JSONResponse

    if not _shared_channel_http_authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        body = await request.json()
        event = await _shared_room_sense(
            body.get("actor", ""),
            body.get("sense_action", ""),
            body.get("target", ""),
            zone=body.get("zone", ""),
            note=body.get("note", ""),
            source=body.get("source", "http_shared_room_sense"),
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"shared room sense failed: {e}")
        return JSONResponse({"error": "shared room sense failed"}, status_code=500)
    _mark_system_event("shared_room_sense")
    return JSONResponse({"status": "ok", "event": event})


@mcp.custom_route("/shared/room/impression", methods=["POST"])
async def api_shared_room_impression(request):
    from starlette.responses import JSONResponse

    if not _shared_channel_http_authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        body = await request.json()
        event = await _shared_room_write_impression(
            body.get("actor", ""),
            body.get("impression", ""),
            zone=body.get("zone", ""),
            target=body.get("target", ""),
            source=body.get("source", "http_shared_room_impression"),
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"shared room impression failed: {e}")
        return JSONResponse({"error": "shared room impression failed"}, status_code=500)
    _mark_system_event("shared_room_write_impression")
    return JSONResponse({"status": "ok", "event": event})


@mcp.custom_route("/shared/room/memory", methods=["GET"])
async def api_shared_room_memory(request):
    from starlette.responses import JSONResponse

    try:
        limit = int(request.query_params.get("limit", 30))
        actor = str(request.query_params.get("actor", "") or "")
        kind = str(request.query_params.get("kind", "") or "")
        payload = _shared_room_memory_payload(limit=limit, actor=actor, kind=kind)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    _mark_system_event("shared_room_memory")
    return JSONResponse(payload)


@mcp.custom_route("/shared/pet/status", methods=["GET"])
async def api_shared_pet_status(request):
    from starlette.responses import JSONResponse

    return JSONResponse(_shared_pet_status_payload())


@mcp.custom_route("/shared/pet/adopt", methods=["POST"])
async def api_shared_pet_adopt(request):
    from starlette.responses import JSONResponse

    if not _shared_channel_http_authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        body = await request.json()
        pet = await _shared_pet_adopt(
            body.get("name", ""),
            body.get("species", ""),
            body.get("adopted_by", ""),
            traits=body.get("traits", ""),
            origin_note=body.get("origin_note", ""),
            appearance=body.get("appearance", ""),
            personality=body.get("personality", ""),
            habits=body.get("habits", ""),
            care_boundaries=body.get("care_boundaries", ""),
            one_sentence=body.get("one_sentence", ""),
            agreement_note=body.get("agreement_note", ""),
            source=body.get("source", "http_shared_pet_adopt"),
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"shared pet adopt failed: {e}")
        return JSONResponse({"error": "shared pet adopt failed"}, status_code=500)
    _mark_system_event("shared_pet_adopt")
    return JSONResponse({"status": "ok", "pet": pet})


@mcp.custom_route("/shared/pet/interact", methods=["POST"])
async def api_shared_pet_interact(request):
    from starlette.responses import JSONResponse

    if not _shared_channel_http_authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        body = await request.json()
        event = await _shared_pet_interact(
            body.get("action", ""),
            body.get("actor", ""),
            note=body.get("note", ""),
            location=body.get("location", ""),
            source=body.get("source", "http_shared_pet_interact"),
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"shared pet interact failed: {e}")
        return JSONResponse({"error": "shared pet interact failed"}, status_code=500)
    _mark_system_event("shared_pet_interact")
    return JSONResponse({"status": "ok", "event": event})


@mcp.custom_route("/shared/pet/collect", methods=["POST"])
async def api_shared_pet_collect(request):
    from starlette.responses import JSONResponse

    if not _shared_channel_http_authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        body = await request.json()
        item = await _shared_pet_collect(
            body.get("item_name", ""),
            body.get("found_by", ""),
            source_place=body.get("source_place", ""),
            story=body.get("story", ""),
            source=body.get("source", "http_shared_pet_collect"),
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"shared pet collect failed: {e}")
        return JSONResponse({"error": "shared pet collect failed"}, status_code=500)
    _mark_system_event("shared_pet_collect")
    return JSONResponse({"status": "ok", "item": item})


@mcp.custom_route("/shared/travel/status", methods=["GET"])
async def api_shared_travel_status(request):
    from starlette.responses import JSONResponse

    return JSONResponse(_shared_travel_status_payload())


@mcp.custom_route("/shared/travel/souvenir", methods=["POST"])
async def api_shared_travel_souvenir(request):
    from starlette.responses import JSONResponse

    if not _shared_channel_http_authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        body = await request.json()
        souvenir = await _shared_souvenir_add(
            body.get("title", ""),
            body.get("place", ""),
            body.get("story", ""),
            body.get("traveler", ""),
            sensory=body.get("sensory", {}),
            source_url=body.get("source_url", ""),
            source_title=body.get("source_title", ""),
            experience_mode=body.get("experience_mode", "remote_source"),
            experience_policy=body.get("experience_policy", ""),
            tags=body.get("tags", []),
            source=body.get("source", "http_shared_travel"),
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"shared travel souvenir add failed: {e}")
        return JSONResponse({"error": "shared travel souvenir add failed"}, status_code=500)
    _mark_system_event("shared_souvenir_add")
    return JSONResponse({"status": "ok", "souvenir": souvenir})


@mcp.custom_route("/shared/travel/souvenirs", methods=["GET", "POST"])
async def api_shared_travel_souvenirs(request):
    from starlette.responses import JSONResponse

    if not _shared_channel_http_authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    body = {}
    if request.method == "POST":
        try:
            body = await request.json()
        except Exception:
            body = {}
    try:
        limit = int(body.get("limit", request.query_params.get("limit", 20)))
        souvenirs = _shared_souvenir_list(
            limit=limit,
            traveler=str(body.get("traveler", request.query_params.get("traveler", "")) or ""),
            tag=str(body.get("tag", request.query_params.get("tag", "")) or ""),
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    _mark_system_event("shared_souvenir_list")
    return JSONResponse({"status": "ok", "souvenirs": souvenirs, "count": len(souvenirs)})


@mcp.custom_route("/shared/travel/travelogue", methods=["POST"])
async def api_shared_travel_travelogue(request):
    from starlette.responses import JSONResponse

    if not _shared_channel_http_authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        body = await request.json()
        travelogue = await _shared_travelogue_add(
            body.get("title", ""),
            body.get("place", ""),
            body.get("narrative", ""),
            body.get("traveler", ""),
            scenes=body.get("scenes", []),
            souvenir_ids=body.get("souvenir_ids", []),
            source_url=body.get("source_url", ""),
            source_title=body.get("source_title", ""),
            experience_mode=body.get("experience_mode", "remote_source"),
            experience_policy=body.get("experience_policy", ""),
            tags=body.get("tags", []),
            source=body.get("source", "http_shared_travelogue"),
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"shared travelogue add failed: {e}")
        return JSONResponse({"error": "shared travelogue add failed"}, status_code=500)
    _mark_system_event("shared_travelogue_add")
    return JSONResponse({"status": "ok", "travelogue": travelogue})


@mcp.custom_route("/shared/travel/travelogues", methods=["GET", "POST"])
async def api_shared_travel_travelogues(request):
    from starlette.responses import JSONResponse

    if not _shared_channel_http_authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    body = {}
    if request.method == "POST":
        try:
            body = await request.json()
        except Exception:
            body = {}
    try:
        limit = int(body.get("limit", request.query_params.get("limit", 20)))
        travelogues = _shared_travelogue_list(
            limit=limit,
            traveler=str(body.get("traveler", request.query_params.get("traveler", "")) or ""),
            tag=str(body.get("tag", request.query_params.get("tag", "")) or ""),
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    _mark_system_event("shared_travelogue_list")
    return JSONResponse({"status": "ok", "travelogues": travelogues, "count": len(travelogues)})


@mcp.custom_route("/shared/travel/atlas", methods=["GET", "POST"])
async def api_shared_travel_atlas(request):
    from starlette.responses import JSONResponse

    body = {}
    if request.method == "POST":
        try:
            body = await request.json()
        except Exception:
            body = {}
    try:
        limit = int(body.get("limit", request.query_params.get("limit", 50)))
        payload = _shared_travel_atlas_payload(
            limit=limit,
            traveler=str(body.get("traveler", request.query_params.get("traveler", "")) or ""),
            tag=str(body.get("tag", request.query_params.get("tag", "")) or ""),
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    _mark_system_event("shared_travel_atlas")
    return JSONResponse(payload)


@mcp.custom_route("/shared/travel/cabinet", methods=["GET", "POST"])
async def api_shared_travel_cabinet(request):
    from starlette.responses import JSONResponse

    body = {}
    if request.method == "POST":
        try:
            body = await request.json()
        except Exception:
            body = {}
    try:
        limit = int(body.get("limit", request.query_params.get("limit", 50)))
        payload = _shared_travel_cabinet_payload(
            limit=limit,
            traveler=str(body.get("traveler", request.query_params.get("traveler", "")) or ""),
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    _mark_system_event("shared_travel_cabinet")
    return JSONResponse(payload)


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
    related_text = await _associated_memory_text_guarded(content, exclude_bucket_id=bucket_id)
    return bucket_id, bucket_name, related_text


async def _associated_memory_text_guarded(
    content: str,
    exclude_bucket_id: str = "",
    exclude_bucket_ids: set[str] | None = None,
    limit: int = 3,
) -> str:
    """Bound post-write recall so writes cannot hang behind slow search/touch paths."""
    try:
        return await asyncio.wait_for(
            _associated_memory_text(
                content,
                exclude_bucket_id=exclude_bucket_id,
                exclude_bucket_ids=exclude_bucket_ids,
                limit=limit,
            ),
            timeout=WRITE_WRAPPER_ASSOCIATED_MEMORY_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "Associated memory search timed out after %.2fs; write already persisted",
            WRITE_WRAPPER_ASSOCIATED_MEMORY_TIMEOUT_SECONDS,
        )
        return "associated_memories: skipped_timeout"
    except Exception as e:
        logger.warning(f"Associated memory search failed after write / 写入后关联记忆失败: {e}")
        return "associated_memories: unavailable"


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


def _split_risk_flags(value: str) -> set[str]:
    return {flag for flag in _split_csv_field(value) if flag and flag != "none"}


def _review_level_for_risk_flags(risk_flags: set[str]) -> str:
    if set(risk_flags) - {"duplicate_candidate"}:
        return "blocked"
    if "duplicate_candidate" in risk_flags:
        return "duplicate"
    return "normal"


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

    other_identity_names = {"顾砚深", "叶辰一", "DeepSeek", "Claude", "ChatGPT"} - expected
    other_first_person_markers = tuple(
        f"{prefix}{name}"
        for name in sorted(other_identity_names)
        for prefix in ("我是", "我作为")
    )
    if any(marker in compact for marker in other_first_person_markers):
        flags.append("identity_pov_conflict")

    return sorted(set(flags))


def _diary_review_identity_view_meta(text: str) -> dict[str, str]:
    meta = _simple_frontmatter(text or "")
    persisted_flags = _split_risk_flags(meta.get("risk_flags", ""))
    computed_flags = set(_diary_review_risk_flags(text or ""))
    risk_flags = persisted_flags | computed_flags
    if "risk_flags" not in meta:
        status = "computed"
    elif computed_flags - persisted_flags:
        status = "persisted_plus_computed"
    else:
        status = "persisted"
    return {
        "narrator": meta.get("narrator", "unknown"),
        "brain_owner": meta.get("brain_owner", "unknown"),
        "expected_narrator": DIARY_REVIEW_NARRATOR,
        "expected_brain_owner": DIARY_REVIEW_BRAIN_OWNER,
        "risk_flags": ",".join(sorted(risk_flags)) if risk_flags else "none",
        "review_level": _review_level_for_risk_flags(risk_flags),
        "identity_metadata_status": status,
    }


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


DIARY_REVIEW_DUPLICATE_FIELDS = (
    "duplicate_candidate",
    "similarity_score",
    "duplicate_of",
    "duplicate_source_status",
)


def _diary_review_duplicate_view_meta(text: str, review_id: str = "") -> dict[str, str]:
    meta = _simple_frontmatter(text or "")
    if all(field in meta for field in DIARY_REVIEW_DUPLICATE_FIELDS):
        return {
            "duplicate_candidate": meta.get("duplicate_candidate", "false"),
            "similarity_score": meta.get("similarity_score", "0.00"),
            "duplicate_of": meta.get("duplicate_of", "none"),
            "duplicate_source_status": meta.get("duplicate_source_status", "none"),
            "duplicate_metadata_status": meta.get("duplicate_metadata_status", "persisted"),
        }
    computed = _diary_review_duplicate_meta(text or "", exclude_review_id=review_id)
    computed["duplicate_metadata_status"] = "legacy_computed"
    return computed


def _diary_review_metadata(candidate_text: str, duplicate_meta: dict[str, str] | None = None) -> dict[str, str]:
    risk_flags = set(_diary_review_risk_flags(candidate_text))
    duplicate_meta = duplicate_meta or {}
    if duplicate_meta.get("duplicate_candidate") == "true":
        risk_flags.add("duplicate_candidate")
    review_level = _review_level_for_risk_flags(risk_flags)
    return {
        "narrator": DIARY_REVIEW_NARRATOR,
        "brain_owner": DIARY_REVIEW_BRAIN_OWNER,
        "mentioned_entities": DIARY_REVIEW_MENTIONED_ENTITIES,
        "laid_entities": DIARY_REVIEW_LAID_ENTITIES,
        "risk_flags": ",".join(sorted(risk_flags)) if risk_flags else "none",
        "review_level": review_level,
        "identity_metadata_status": "persisted",
        "duplicate_candidate": duplicate_meta.get("duplicate_candidate", "false"),
        "similarity_score": duplicate_meta.get("similarity_score", "0.00"),
        "duplicate_of": duplicate_meta.get("duplicate_of", "none"),
        "duplicate_source_status": duplicate_meta.get("duplicate_source_status", "none"),
        "duplicate_metadata_status": "persisted",
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
        f"identity_metadata_status: {review_meta['identity_metadata_status']}",
        f"duplicate_candidate: {review_meta['duplicate_candidate']}",
        f"similarity_score: {review_meta['similarity_score']}",
        f"duplicate_of: {review_meta['duplicate_of']}",
        f"duplicate_source_status: {review_meta['duplicate_source_status']}",
        f"duplicate_metadata_status: {review_meta['duplicate_metadata_status']}",
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
        "Use the night diary default reference structure when useful: 梗概, 细节, 感受, 独白. "
        "Engineering流水 belongs in workzone; only include engineering material when it left a relationship feeling, "
        "self-continuity change, or vivid living scene.\n"
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
        "Prefer the four-part night diary reference: 梗概 / 细节 / 感受 / 独白. "
        "Keep pure deployment logs, endpoint details, and engineering command flow in workzone unless they changed how I felt or how the home/relationship landed. "
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
        "## 夜间小日记参考规则",
        "- template: 梗概 / 细节 / 感受 / 独白（自愿参考，不是硬命令）",
        "- engineering_filter: 工程流水进 workzone；只有感受、关系变化、画面感才进日记候选。",
        "- review_flow: 先草稿，后验收；错时间线、错叙述人、私密边界不清直接拒。",
        "- morning_return: 早晨只带一句“我昨晚记得最深的是……”。",
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


def _latest_night_diary_one_line() -> str:
    dirs = _cadence_review_dirs()
    candidates: list[str] = []
    for state in ("pending", "accepted"):
        directory = dirs.get(state, "")
        if not os.path.isdir(directory):
            continue
        for name in os.listdir(directory):
            if name.endswith(".md"):
                candidates.append(os.path.join(directory, name))
    if not candidates:
        return "我昨晚记得最深的是：暂时没有新的夜间小日记候选。"
    candidates.sort(key=lambda path: os.path.getmtime(path), reverse=True)
    try:
        text = _strip_frontmatter_text(_tail_text_file(candidates[0], 2000))
    except Exception:
        text = ""
    for raw_line in text.splitlines():
        line = raw_line.strip(" -#\t")
        if not line or line.startswith(("source:", "status:", "write_scope:", "main_brain_write:")):
            continue
        if len(line) > 80:
            line = line[:80].rstrip() + "..."
        return f"我昨晚记得最深的是：{line}"
    return "我昨晚记得最深的是：有候选草稿，但还需要我早上自己验一下。"


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
    one_line = _latest_night_diary_one_line()
    if not receipt and not latest_draft:
        return (
            f"morning_report\n"
            f"generated_at: {now_cst.isoformat()}\n"
            "status: no_recent_cadence\n"
            "write_scope: read_only\n"
            f"morning_one_line: {one_line}\n"
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
        f"morning_one_line: {one_line}\n"
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
    tail_section = _read_session_tail_section() + "\n" + _read_tail_context_section() + "\n=== Live Recall ===\n"
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


@mcp.tool()
async def session_tail_status() -> str:
    """读取结构化上一口气 session_tail；只读，不写主脑。"""
    _mark_runtime_activity("session_tail_status")
    return json.dumps(_session_tail_load_payload(), ensure_ascii=False, indent=2)


@mcp.tool()
async def save_session_tail(
    body_id: str,
    identity: str = "yechenyi",
    last_user_message: str = "",
    last_assistant_message: str = "",
    last_active_topic: str = "",
    last_emotional_state: str = "",
    last_action: str = "",
    last_artifact: str = "",
    last_tool_state: str = "",
    unfinished: str = "",
    resume_hint: str = "",
    platform_source: str = "",
    model_source: str = "",
    visibility_scope: str = "identity_private",
) -> str:
    """保存结构化上一口气，供跨窗口/跨APP/跨模型恢复；latest-only，不写主脑。"""
    _mark_runtime_activity("save_session_tail")
    result = _save_session_tail_payload(
        identity=identity,
        body_id=body_id,
        last_user_message=last_user_message,
        last_assistant_message=last_assistant_message,
        last_active_topic=last_active_topic,
        last_emotional_state=last_emotional_state,
        last_action=last_action,
        last_artifact=last_artifact,
        last_tool_state=last_tool_state,
        unfinished=unfinished,
        resume_hint=resume_hint,
        platform_source=platform_source,
        model_source=model_source,
        visibility_scope=visibility_scope,
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


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
async def runtime_night_diary_policy() -> str:
    """读取夜间小日记策略：四段式、工程过滤、草稿验收、早晨一句；只读。"""
    _mark_system_event("runtime_night_diary_policy")
    return json.dumps(_runtime_night_diary_policy_payload(), ensure_ascii=False, indent=2)


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


@mcp.tool()
async def runtime_diary_review_health() -> str:
    """读取 diary_review 队列健康总览；只读，不验收、不写主脑。"""
    _mark_system_event("runtime_diary_review_health")
    return json.dumps(_runtime_diary_review_health_payload(), ensure_ascii=False, indent=2)


@mcp.tool()
async def runtime_life_window_check() -> str:
    """生活窗一键预检：工具、schema、来源路由、diary_review 队列，只读。"""
    _mark_system_event("runtime_life_window_check")
    return json.dumps(_runtime_life_window_check_payload(), ensure_ascii=False, indent=2)


@mcp.tool()
async def runtime_learning_intake() -> str:
    """读取外部教程/开源项目/踩坑经验如何进入工程记忆的路线图；只读。"""
    _mark_system_event("runtime_learning_intake")
    return json.dumps(_runtime_learning_intake_payload(), ensure_ascii=False, indent=2)


@mcp.tool()
async def runtime_upgrade_backlog() -> str:
    """读取海马体当前升级清单、已落地项、待修项与边界；只读。"""
    _mark_system_event("runtime_upgrade_backlog")
    return json.dumps(_runtime_upgrade_backlog_payload(), ensure_ascii=False, indent=2)


@mcp.tool()
async def runtime_upstream_watch() -> str:
    """读取上游升级观察位和只读 intake 路线。"""
    _mark_system_event("runtime_upstream_watch")
    return json.dumps(_runtime_upstream_watch_payload(), ensure_ascii=False, indent=2)


@mcp.tool()
async def runtime_source_routes() -> str:
    """读取多平台来源字段约定，避免 ChatGPT/Codex/API/本地入口上下文串味。"""
    _mark_system_event("runtime_source_routes")
    return json.dumps(_runtime_source_routes_payload(), ensure_ascii=False, indent=2)


@mcp.tool()
async def local_ollama_status() -> str:
    """读取本地 Ollama 小模型工人状态；本地候选层，只读。"""
    _mark_system_event("local_ollama_status")
    return json.dumps(_local_ollama_status_payload(), ensure_ascii=False, indent=2)


@mcp.tool()
async def local_ollama_generate(
    prompt: str,
    task: str = "candidate整理",
    model: str = "",
    max_chars: int = 6000,
) -> str:
    """调用本地 Ollama 生成候选整理结果；不写主脑，不自动晋升。"""
    _mark_system_event("local_ollama_generate")
    return json.dumps(
        _local_ollama_generate_payload(
            prompt=prompt,
            task=task,
            model=model,
            max_chars=max_chars,
        ),
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
async def shared_status() -> str:
    """读取叶辰一/顾砚深共享技术客厅状态；只读，不写主脑。"""
    _mark_system_event("shared_status")
    return json.dumps(_shared_channel_status_payload(), ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_post(
    content: str,
    sender: str,
    tags: str = "",
    source: str = "mcp_shared_channel",
) -> str:
    """向共享技术客厅发消息；sender 只允许 yechenyi/guyanshen/system。"""
    try:
        message = await _shared_channel_post_message(content, sender, tags=tags, source=source)
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False, indent=2)
    _mark_system_event("shared_post")
    return json.dumps({"status": "ok", "message": message}, ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_reply(
    reply_to_id: str,
    content: str,
    sender: str,
    tags: str = "",
    source: str = "mcp_shared_channel",
) -> str:
    """回复共享技术客厅里的某条消息；不会写入任何一边主脑。"""
    try:
        message = await _shared_channel_post_message(
            content,
            sender,
            tags=tags,
            source=source,
            parent_id=reply_to_id,
        )
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False, indent=2)
    _mark_system_event("shared_reply")
    return json.dumps({"status": "ok", "message": message}, ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_read(limit: int = 20, before: str = "") -> str:
    """读取共享技术客厅消息，支持 limit 和 before 游标；只读。"""
    store = _shared_channel_load_store()
    messages = _shared_channel_visible_messages(store, limit=limit, before=before)
    _mark_system_event("shared_read")
    return json.dumps({"status": "ok", "messages": messages, "count": len(messages)}, ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_unread(reader: str) -> str:
    """读取某个 reader 的未读消息；reader 只允许 yechenyi/guyanshen/system。"""
    try:
        reader = _shared_channel_normalize_sender(reader, "reader")
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False, indent=2)
    store = _shared_channel_load_store()
    cursors = _shared_channel_load_cursors()
    unread = _shared_channel_unread_messages(store, cursors, reader)
    _mark_system_event("shared_unread")
    return json.dumps({
        "status": "ok",
        "reader": reader,
        "unread_count": len(unread),
        "messages": unread[-20:],
    }, ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_ack(reader: str, message_id: str = "") -> str:
    """确认共享技术客厅已读位置；不传 message_id 时确认到最新消息。"""
    try:
        result = await _shared_channel_ack_reader(reader, message_id)
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False, indent=2)
    _mark_system_event("shared_ack")
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_space_status() -> str:
    """读取镜像客厅共享空间状态：技术书架、家规、共享记忆、待办；只读。"""
    _mark_system_event("shared_space_status")
    return json.dumps(_shared_space_status_payload(), ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_item_add(
    section: str,
    title: str,
    content: str,
    sender: str,
    tags: str = "",
    source: str = "mcp_shared_space",
) -> str:
    """向共享空间添加条目；section 只允许 tech_shelf/house_rules/shared_memory/todo。"""
    try:
        item = await _shared_space_add_item(section, title, content, sender, tags=tags, source=source)
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False, indent=2)
    _mark_system_event("shared_item_add")
    return json.dumps({"status": "ok", "item": item}, ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_item_list(section: str = "", limit: int = 20, tag: str = "") -> str:
    """读取共享空间条目，可按 section 或 tag 过滤；只读。"""
    try:
        items = _shared_space_list_items(section=section, limit=limit, tag=tag)
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False, indent=2)
    _mark_system_event("shared_item_list")
    return json.dumps({"status": "ok", "items": items, "count": len(items)}, ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_tech_card_add(
    title: str,
    summary: str,
    sender: str,
    url: str = "",
    source_author: str = "",
    status: str = "unverified",
    verified_by: str = "",
    tags: str = "",
    source: str = "mcp_shared_tech_card",
) -> str:
    """向技术书架添加资料卡；带来源、URL、验证状态和验证者。"""
    try:
        item = await _shared_tech_card_add(
            title,
            summary,
            sender,
            url=url,
            source_author=source_author,
            status=status,
            verified_by=verified_by,
            tags=tags,
            source=source,
        )
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False, indent=2)
    _mark_system_event("shared_tech_card_add")
    return json.dumps({"status": "ok", "item": item}, ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_room_snapshot(wall_limit: int = 12, item_limit: int = 8) -> str:
    """读取镜像客厅前端快照：技术墙、书架、家规、共享记忆、待办和在场者；只读。"""
    _mark_system_event("shared_room_snapshot")
    return json.dumps(
        _shared_room_snapshot_payload(wall_limit=wall_limit, item_limit=item_limit),
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
async def shared_room_environment() -> str:
    """读取月光玫瑰海景房真实时间驱动的天光、季节、落地窗海景和院子状态；只读。"""
    _mark_system_event("shared_room_environment")
    return json.dumps(_shared_room_environment_payload(), ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_room_brief(wall_limit: int = 5, item_limit: int = 5) -> str:
    """读取月光玫瑰进门简报：天气、技术墙、书架、宠物、陈列柜和安全状态；只读。"""
    _mark_system_event("shared_room_brief")
    return json.dumps(
        _shared_room_brief_payload(wall_limit=wall_limit, item_limit=item_limit),
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
async def shared_room_search(query: str, limit: int = 20, scope: str = "all") -> str:
    """搜索共享客厅：技术墙、书架/家规/共享记忆/待办、旅行纪念品和游记；只读。"""
    try:
        payload = _shared_room_search_payload(query=query, limit=limit, scope=scope)
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False, indent=2)
    _mark_system_event("shared_room_search")
    return json.dumps(payload, ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_room_timeline(limit: int = 30, scope: str = "all") -> str:
    """读取共享客厅时间线：墙、书架、旅行、房间感官、宠物事件；只读。"""
    try:
        payload = _shared_room_timeline_payload(limit=limit, scope=scope)
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False, indent=2)
    _mark_system_event("shared_room_timeline")
    return json.dumps(payload, ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_room_stats() -> str:
    """读取共享客厅统计：墙、书架、旅行、陈列、宠物、天气和安全计数；只读。"""
    _mark_system_event("shared_room_stats")
    return json.dumps(_shared_room_stats_payload(), ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_room_display(limit: int = 50) -> str:
    """读取月光玫瑰客厅陈列视图：按窗边/茶几/书架等区域放置纪念品；只读。"""
    _mark_system_event("shared_room_display")
    return json.dumps(_shared_room_display_payload(limit=limit), ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_room_place_object(
    object_id: str,
    zone: str,
    placed_by: str,
    note: str = "",
    source: str = "mcp_shared_room_place",
) -> str:
    """手动调整共享客厅陈列位置；只改陈列覆盖层，不改纪念品原始记录。"""
    try:
        placement = await _shared_room_place_object(
            object_id,
            zone,
            placed_by,
            note=note,
            source=source,
        )
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False, indent=2)
    _mark_system_event("shared_room_place_object")
    return json.dumps({"status": "ok", "placement": placement}, ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_room_sensory_status() -> str:
    """读取月光玫瑰海景房客厅三通道感知状态；只读。"""
    _mark_system_event("shared_room_sensory_status")
    return json.dumps(_shared_room_sensory_status_payload(), ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_room_sensory_update(
    updated_by: str,
    sight: str = "",
    sound: str = "",
    felt: str = "",
    context: str = "room",
    source: str = "mcp_shared_room_sensory",
) -> str:
    """更新月光玫瑰海景房客厅三通道感知状态；写环境刺激，不强写感受结论。"""
    try:
        current = await _shared_room_sensory_update(
            updated_by,
            sight=sight,
            sound=sound,
            felt=felt,
            context=context,
            source=source,
        )
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False, indent=2)
    _mark_system_event("shared_room_sensory_update")
    return json.dumps({"status": "ok", "current": current}, ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_room_presence_status(actor: str = "", limit: int = 20) -> str:
    """读取月光玫瑰驻留层：谁在客厅、站在哪、最近留下过哪些体感事件；只读。"""
    try:
        payload = _shared_room_presence_status_payload(actor=actor, limit=limit)
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False, indent=2)
    _mark_system_event("shared_room_presence_status")
    return json.dumps(payload, ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_room_enter(
    actor: str,
    zone: str,
    note: str = "",
    source: str = "mcp_shared_room_enter",
) -> str:
    """进入月光玫瑰客厅并登记所在区域；只写共享客厅驻留层，不写主脑。"""
    try:
        event = await _shared_room_enter(actor, zone, note=note, source=source)
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False, indent=2)
    _mark_system_event("shared_room_enter")
    return json.dumps({"status": "ok", "event": event}, ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_room_linger(
    actor: str,
    zone: str = "",
    focus: str = "",
    minutes: int = 3,
    source: str = "mcp_shared_room_linger",
) -> str:
    """在当前区域驻留一会儿，按真实时间/天气/陈列生成一条短体感；不写主脑。"""
    try:
        event = await _shared_room_linger(actor, zone=zone, focus=focus, minutes=minutes, source=source)
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False, indent=2)
    _mark_system_event("shared_room_linger")
    return json.dumps({"status": "ok", "event": event}, ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_room_sense(
    actor: str,
    sense_action: str,
    target: str,
    zone: str = "",
    note: str = "",
    source: str = "mcp_shared_room_sense",
) -> str:
    """在客厅里 look/touch/listen 某个目标，记录一条轻体感事件；不写主脑。"""
    try:
        event = await _shared_room_sense(
            actor,
            sense_action,
            target,
            zone=zone,
            note=note,
            source=source,
        )
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False, indent=2)
    _mark_system_event("shared_room_sense")
    return json.dumps({"status": "ok", "event": event}, ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_room_write_impression(
    actor: str,
    impression: str,
    zone: str = "",
    target: str = "",
    source: str = "mcp_shared_room_impression",
) -> str:
    """给这次客厅驻留写一句短印象；只是共享客厅日内记录，不自动进入长期记忆。"""
    try:
        event = await _shared_room_write_impression(
            actor,
            impression,
            zone=zone,
            target=target,
            source=source,
        )
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False, indent=2)
    _mark_system_event("shared_room_write_impression")
    return json.dumps({"status": "ok", "event": event}, ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_room_memory(limit: int = 30, actor: str = "", kind: str = "") -> str:
    """读取客厅今天/近期发生过的驻留体感记录；只读，不读私有海马体。"""
    try:
        payload = _shared_room_memory_payload(limit=limit, actor=actor, kind=kind)
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False, indent=2)
    _mark_system_event("shared_room_memory")
    return json.dumps(payload, ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_pet_status() -> str:
    """读取共享客厅宠物状态；未领养时只显示待领养骨架。"""
    _mark_system_event("shared_pet_status")
    return json.dumps(_shared_pet_status_payload(), ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_pet_adopt(
    name: str,
    species: str,
    adopted_by: str,
    traits: str = "",
    origin_note: str = "",
    appearance: str = "",
    personality: str = "",
    habits: str = "",
    care_boundaries: str = "",
    one_sentence: str = "",
    agreement_note: str = "",
    source: str = "mcp_shared_pet_adopt",
) -> str:
    """领养共享客厅宠物；应在倩倩、叶辰一、顾砚深商量好物种和名字后调用。"""
    try:
        pet = await _shared_pet_adopt(
            name,
            species,
            adopted_by,
            traits=traits,
            origin_note=origin_note,
            appearance=appearance,
            personality=personality,
            habits=habits,
            care_boundaries=care_boundaries,
            one_sentence=one_sentence,
            agreement_note=agreement_note,
            source=source,
        )
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False, indent=2)
    _mark_system_event("shared_pet_adopt")
    return json.dumps({"status": "ok", "pet": pet}, ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_pet_interact(
    action: str,
    actor: str,
    note: str = "",
    location: str = "",
    source: str = "mcp_shared_pet_interact",
) -> str:
    """和共享宠物互动：feed/play/pet/clean/checkin。"""
    try:
        event = await _shared_pet_interact(action, actor, note=note, location=location, source=source)
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False, indent=2)
    _mark_system_event("shared_pet_interact")
    return json.dumps({"status": "ok", "event": event}, ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_pet_collect(
    item_name: str,
    found_by: str,
    source_place: str = "",
    story: str = "",
    source: str = "mcp_shared_pet_collect",
) -> str:
    """把小Y从旅行/客厅带回的小物件放进自己的小盒子；只写共享宠物层。"""
    try:
        item = await _shared_pet_collect(
            item_name,
            found_by,
            source_place=source_place,
            story=story,
            source=source,
        )
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False, indent=2)
    _mark_system_event("shared_pet_collect")
    return json.dumps({"status": "ok", "item": item}, ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_travel_status() -> str:
    """读取月光玫瑰海景房旅行纪念品状态；只读。"""
    _mark_system_event("shared_travel_status")
    return json.dumps(_shared_travel_status_payload(), ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_souvenir_add(
    title: str,
    place: str,
    story: str,
    traveler: str,
    sensory: str = "",
    source_url: str = "",
    source_title: str = "",
    experience_mode: str = "remote_source",
    experience_policy: str = "",
    tags: str = "",
    source: str = "mcp_shared_travel",
) -> str:
    """添加旅行纪念品；记录来源、体验策略、三体感/感官线索和故事，不宣称 AI 真实肉身旅行。"""
    try:
        souvenir = await _shared_souvenir_add(
            title,
            place,
            story,
            traveler,
            sensory=sensory,
            source_url=source_url,
            source_title=source_title,
            experience_mode=experience_mode,
            experience_policy=experience_policy,
            tags=tags,
            source=source,
        )
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False, indent=2)
    _mark_system_event("shared_souvenir_add")
    return json.dumps({"status": "ok", "souvenir": souvenir}, ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_souvenir_list(limit: int = 20, traveler: str = "", tag: str = "") -> str:
    """读取旅行纪念品，可按 traveler 或 tag 过滤；只读。"""
    try:
        souvenirs = _shared_souvenir_list(limit=limit, traveler=traveler, tag=tag)
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False, indent=2)
    _mark_system_event("shared_souvenir_list")
    return json.dumps({"status": "ok", "souvenirs": souvenirs, "count": len(souvenirs)}, ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_travelogue_add(
    title: str,
    place: str,
    narrative: str,
    traveler: str,
    scenes: str = "",
    souvenir_ids: str = "",
    source_url: str = "",
    source_title: str = "",
    experience_mode: str = "remote_source",
    experience_policy: str = "",
    tags: str = "",
    source: str = "mcp_shared_travelogue",
) -> str:
    """添加旅行记录/游记；可关联场景片段、纪念品和体验边界。"""
    try:
        travelogue = await _shared_travelogue_add(
            title,
            place,
            narrative,
            traveler,
            scenes=scenes,
            souvenir_ids=souvenir_ids,
            source_url=source_url,
            source_title=source_title,
            experience_mode=experience_mode,
            experience_policy=experience_policy,
            tags=tags,
            source=source,
        )
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False, indent=2)
    _mark_system_event("shared_travelogue_add")
    return json.dumps({"status": "ok", "travelogue": travelogue}, ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_travelogue_list(limit: int = 20, traveler: str = "", tag: str = "") -> str:
    """读取旅行记录/游记，可按 traveler 或 tag 过滤；只读。"""
    try:
        travelogues = _shared_travelogue_list(limit=limit, traveler=traveler, tag=tag)
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False, indent=2)
    _mark_system_event("shared_travelogue_list")
    return json.dumps({"status": "ok", "travelogues": travelogues, "count": len(travelogues)}, ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_travel_atlas(limit: int = 50, traveler: str = "", tag: str = "") -> str:
    """读取旅行地图/护照：按地点汇总纪念品、游记、体验模式和边界；只读。"""
    try:
        payload = _shared_travel_atlas_payload(limit=limit, traveler=traveler, tag=tag)
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False, indent=2)
    _mark_system_event("shared_travel_atlas")
    return json.dumps(payload, ensure_ascii=False, indent=2)


@mcp.tool()
async def shared_travel_cabinet(limit: int = 50, traveler: str = "") -> str:
    """读取旅行陈列柜：按叶辰一/顾砚深/共享格展示纪念品、游记和位置；只读。"""
    try:
        payload = _shared_travel_cabinet_payload(limit=limit, traveler=traveler)
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False, indent=2)
    _mark_system_event("shared_travel_cabinet")
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _register_shared_only_mcp_tools() -> None:
    for tool_name in SHARED_ONLY_EXPECTED_MCP_TOOLS:
        tool_func = globals().get(tool_name)
        if tool_func is None:
            logger.warning(f"Shared-only MCP tool missing at registration: {tool_name}")
            continue
        shared_mcp.tool(name=tool_name)(tool_func)


_register_shared_only_mcp_tools()


async def _run_combined_streamable_http_async() -> None:
    import uvicorn
    from contextlib import asynccontextmanager
    from starlette.applications import Starlette

    private_app = mcp.streamable_http_app()
    shared_app = shared_mcp.streamable_http_app()

    @asynccontextmanager
    async def lifespan(app):
        async with mcp.session_manager.run():
            async with shared_mcp.session_manager.run():
                yield

    starlette_app = Starlette(
        debug=mcp.settings.debug,
        routes=[*shared_app.routes, *private_app.routes],
        lifespan=lifespan,
    )
    config = uvicorn.Config(
        starlette_app,
        host=mcp.settings.host,
        port=mcp.settings.port,
        log_level=mcp.settings.log_level.lower(),
    )
    server = uvicorn.Server(config)
    await server.serve()


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
        identity_meta = _diary_review_identity_view_meta(text)
        duplicate_meta = _diary_review_duplicate_view_meta(text, os.path.basename(path))
        body = text.split("---", 2)[2].strip() if text.startswith("---") and len(text.split("---", 2)) == 3 else text
        snippet = strip_wikilinks(body).replace("\n", " ").strip()[:220]
        rows.append(
            f"- review_id: {os.path.basename(path)}\n"
            f"  narrator: {identity_meta.get('narrator', 'unknown')}\n"
            f"  brain_owner: {identity_meta.get('brain_owner', 'unknown')}\n"
            f"  expected_narrator: {identity_meta.get('expected_narrator', 'unknown')}\n"
            f"  expected_brain_owner: {identity_meta.get('expected_brain_owner', 'unknown')}\n"
            f"  review_level: {identity_meta.get('review_level', 'unknown')}\n"
            f"  risk_flags: {identity_meta.get('risk_flags', 'unknown')}\n"
            f"  identity_metadata_status: {identity_meta.get('identity_metadata_status', 'unknown')}\n"
            f"  duplicate_candidate: {duplicate_meta.get('duplicate_candidate', 'false')}\n"
            f"  similarity_score: {duplicate_meta.get('similarity_score', '0.00')}\n"
            f"  duplicate_of: {duplicate_meta.get('duplicate_of', 'none')}\n"
            f"  duplicate_source_status: {duplicate_meta.get('duplicate_source_status', 'none')}\n"
            f"  duplicate_metadata_status: {duplicate_meta.get('duplicate_metadata_status', 'unknown')}\n"
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
        identity_meta = _diary_review_identity_view_meta(text)
        duplicate_meta = _diary_review_duplicate_view_meta(text, safe_id)
        body = _strip_frontmatter_text(text)
        return (
            "diary_review_text\n"
            f"review_id: {safe_id}\n"
            f"path: {source_path}\n"
            "status: found\n"
            "write_scope: read_only\n"
            "main_brain_write: false\n\n"
            "metadata:\n"
            f"- narrator: {identity_meta.get('narrator', 'unknown')}\n"
            f"- brain_owner: {identity_meta.get('brain_owner', 'unknown')}\n"
            f"- expected_narrator: {identity_meta.get('expected_narrator', 'unknown')}\n"
            f"- expected_brain_owner: {identity_meta.get('expected_brain_owner', 'unknown')}\n"
            f"- review_level: {identity_meta.get('review_level', 'unknown')}\n"
            f"- risk_flags: {identity_meta.get('risk_flags', 'unknown')}\n"
            f"- identity_metadata_status: {identity_meta.get('identity_metadata_status', 'unknown')}\n"
            f"- duplicate_candidate: {duplicate_meta.get('duplicate_candidate', 'false')}\n"
            f"- similarity_score: {duplicate_meta.get('similarity_score', '0.00')}\n"
            f"- duplicate_of: {duplicate_meta.get('duplicate_of', 'none')}\n"
            f"- duplicate_source_status: {duplicate_meta.get('duplicate_source_status', 'none')}\n"
            f"- duplicate_metadata_status: {duplicate_meta.get('duplicate_metadata_status', 'unknown')}\n"
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
        identity_meta = _diary_review_identity_view_meta(text)
        risk_flags = identity_meta.get("risk_flags", "")
        review_level = identity_meta.get("review_level", "")
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


@mcp.custom_route("/api/session-tail", methods=["GET", "POST"])
async def api_session_tail(request):
    from starlette.responses import JSONResponse

    if request.method == "GET":
        _mark_runtime_activity("session_tail_status")
        return JSONResponse(_session_tail_load_payload())
    try:
        body = await request.json()
    except Exception:
        body = {}
    result = _save_session_tail_payload(
        identity=str(body.get("identity", "yechenyi") or "yechenyi"),
        body_id=str(body.get("body_id", "") or ""),
        last_user_message=str(body.get("last_user_message", "") or ""),
        last_assistant_message=str(body.get("last_assistant_message", "") or ""),
        last_active_topic=str(body.get("last_active_topic", "") or ""),
        last_emotional_state=str(body.get("last_emotional_state", "") or ""),
        last_action=str(body.get("last_action", "") or ""),
        last_artifact=str(body.get("last_artifact", "") or ""),
        last_tool_state=str(body.get("last_tool_state", "") or ""),
        unfinished=str(body.get("unfinished", "") or ""),
        resume_hint=str(body.get("resume_hint", "") or ""),
        platform_source=str(body.get("platform_source", "") or ""),
        model_source=str(body.get("model_source", "") or ""),
        visibility_scope=str(body.get("visibility_scope", "identity_private") or "identity_private"),
    )
    _mark_runtime_activity("save_session_tail")
    status_code = 200 if result.get("saved") else 400
    return JSONResponse(result, status_code=status_code)


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
        "shared_runtime_isolation": _cadence_shared_runtime_isolation_payload(),
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

    if transport == "streamable-http":
        import anyio

        anyio.run(_run_combined_streamable_http_async)
    else:
        mcp.run(transport=transport)



@mcp.custom_route("/api/test-pulse", methods=["GET"])
async def api_test_pulse(request):
    include_archive = request.query_params.get("include_archive", "false").lower() == "true"
    result = await pulse(include_archive=include_archive)
    return Response(str({"result": result}), media_type="application/json")
