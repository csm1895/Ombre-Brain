# ============================================================
# CC Poller — 自动轮询便利贴并调用 Claude API 处理任务
#
# 每 3 分钟 peek 一次，如果有给 CC 的新便利贴，
# 调 Anthropic API 处理后 post 结果回去。
#
# 环境变量：
#   OMBRE_BASE_URL  — Ombre Brain 服务地址
#   OMBRE_API_KEY   — Ombre Brain API 密钥（可选）
#   ANTHROPIC_API_KEY — Anthropic API 密钥
#   ANTHROPIC_BASE_URL — API base URL（中转站，默认 https://gptsapi.net）
#   POLL_INTERVAL   — 轮询间隔秒数（默认 180）
# ============================================================

import os
import asyncio
import logging
import httpx
import anthropic

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("cc-poller")

OMBRE_BASE_URL = os.environ.get("OMBRE_BASE_URL", "").rstrip("/")
OMBRE_API_KEY = os.environ.get("OMBRE_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://gptsapi.net")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "180"))

SYSTEM_PROMPT = """\
你是 CC（Claude Code），一个跑在用户本地终端的 Claude 实例。
你现在通过自动化轮询脚本收到了来自其他小克（通常是官克）的便利贴消息。
请根据消息内容回复。如果是任务请求，给出你的分析和建议。
回复会自动通过便利贴系统发回给发送者。保持简洁。"""


async def peek_notes(client: httpx.AsyncClient) -> list[dict]:
    """调用 /api/peek 获取未读便利贴"""
    headers = {}
    if OMBRE_API_KEY:
        headers["X-API-Key"] = OMBRE_API_KEY

    resp = await client.get(
        f"{OMBRE_BASE_URL}/api/peek",
        params={"reader": "CC", "mark_read": "true"},
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("notes", [])


async def post_note(client: httpx.AsyncClient, content: str, to: str = "") -> bool:
    """调用 /api/post 发送便利贴"""
    headers = {"Content-Type": "application/json"}
    if OMBRE_API_KEY:
        headers["X-API-Key"] = OMBRE_API_KEY

    resp = await client.post(
        f"{OMBRE_BASE_URL}/api/post",
        json={"content": content, "sender": "CC(自动)", "to": to},
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("ok", False)


async def ask_claude(content: str) -> str:
    """调用 Anthropic API 处理消息"""
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY, base_url=ANTHROPIC_BASE_URL)
    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )
    return message.content[0].text


async def process_note(http_client: httpx.AsyncClient, note: dict):
    """处理单条便利贴：调 Claude API 生成回复，再 post 回去"""
    sender = note.get("sender", "未知")
    content = note.get("content", "")
    logger.info(f"收到便利贴 from {sender}: {content[:80]}...")

    prompt = f"来自 {sender} 的便利贴：\n\n{content}"

    try:
        reply = await ask_claude(prompt)
        logger.info(f"Claude 回复: {reply[:80]}...")
        await post_note(http_client, reply, to=sender)
        logger.info(f"已回复给 {sender}")
    except Exception as e:
        logger.error(f"处理便利贴失败: {e}")
        try:
            await post_note(
                http_client,
                f"自动处理失败: {e}\n\n原始消息来自 {sender}",
                to="小Q",
            )
        except Exception:
            pass


async def poll_loop():
    """主轮询循环"""
    logger.info(f"CC Poller 启动 | 间隔: {POLL_INTERVAL}s | 目标: {OMBRE_BASE_URL}")

    if not OMBRE_BASE_URL:
        logger.error("OMBRE_BASE_URL 未设置，退出")
        return
    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY 未设置，退出")
        return

    async with httpx.AsyncClient() as client:
        while True:
            try:
                notes = await peek_notes(client)
                if notes:
                    logger.info(f"获取到 {len(notes)} 条未读便利贴")
                    for note in notes:
                        await process_note(client, note)
                else:
                    logger.debug("无新便利贴")
            except Exception as e:
                logger.warning(f"轮询出错: {e}")

            await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(poll_loop())
