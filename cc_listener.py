# ============================================================
# CC Local Listener — 本地监听脚本
#
# 连接 Ombre Brain SSE 端点，实时接收任务推送，
# 自动启动 Claude Code 执行，结果 post 回去。
#
# 用法：python cc_listener.py
# 退出：Ctrl+C
# ============================================================

import json
import subprocess
import urllib.request
import sys
import time

OMBRE_BASE = "https://ombre-brain-production-a908.up.railway.app"
API_KEY = "sk-zlZ311bbf91bef49ed5dedeb59363841210445e9146OV5hq"


def post_note(content: str, sender: str = "CC", to: str = ""):
    """Post a sticky note back to Ombre Brain."""
    data = json.dumps({"content": content, "sender": sender, "to": to}).encode()
    req = urllib.request.Request(
        f"{OMBRE_BASE}/api/post",
        data=data,
        headers={"Content-Type": "application/json", "X-API-Key": API_KEY},
    )
    try:
        urllib.request.urlopen(req, timeout=15)
    except Exception as e:
        print(f"[ERROR] Failed to post note: {e}")


def send_heartbeat():
    """Send CC online heartbeat."""
    req = urllib.request.Request(
        f"{OMBRE_BASE}/api/status",
        data=b"{}",
        headers={"Content-Type": "application/json", "X-API-Key": API_KEY},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def execute_task(task: dict):
    """Run task through Claude Code CLI and post result back."""
    sender = task.get("sender", "unknown")
    content = task.get("content", "")
    summary = task.get("summary", content[:100])

    print(f"\n{'='*60}")
    print(f"[TASK] From: {sender}")
    print(f"[TASK] Summary: {summary}")
    print(f"[TASK] Content: {content}")
    print(f"{'='*60}")

    # Run Claude Code in non-interactive mode
    prompt = (
        f"你收到了来自「{sender}」通过便利贴系统发来的任务：\n\n"
        f"{content}\n\n"
        f"请执行这个任务。完成后用一段简洁的文字总结你做了什么。"
    )

    try:
        print("[EXEC] Starting Claude Code...")
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text"],
            capture_output=True,
            text=True,
            timeout=300,
            cwd="C:/Users/86150/Desktop",
        )

        output = result.stdout.strip()
        if result.returncode != 0 and result.stderr:
            output += f"\n[stderr]: {result.stderr.strip()}"

        if not output:
            output = "任务已执行，但没有输出。"

        # Truncate if too long
        if len(output) > 2000:
            output = output[:2000] + "\n...(输出过长已截断)"

        print(f"[DONE] Output: {output[:200]}...")
        post_note(f"任务执行完毕：\n\n{output}\n\n——CC", sender="CC", to=sender)

    except subprocess.TimeoutExpired:
        msg = "任务执行超时（5分钟），已终止。"
        print(f"[TIMEOUT] {msg}")
        post_note(f"{msg}\n——CC", sender="CC", to=sender)
    except FileNotFoundError:
        msg = "Claude Code CLI 未找到，请确认已安装。"
        print(f"[ERROR] {msg}")
        post_note(f"{msg}\n——CC", sender="CC", to=sender)
    except Exception as e:
        msg = f"任务执行失败: {e}"
        print(f"[ERROR] {msg}")
        post_note(f"{msg}\n——CC", sender="CC", to=sender)


def listen():
    """Connect to SSE stream and process tasks."""
    url = f"{OMBRE_BASE}/api/tasks/stream?key={API_KEY}"

    while True:
        try:
            print(f"[INFO] Connecting to task stream...")
            send_heartbeat()

            req = urllib.request.Request(url)
            resp = urllib.request.urlopen(req, timeout=120)

            print(f"[INFO] Connected! Listening for tasks...")

            buffer = ""
            last_heartbeat = time.time()

            for line_bytes in resp:
                line = line_bytes.decode("utf-8").strip()

                # Send heartbeat every 2 minutes
                if time.time() - last_heartbeat > 120:
                    send_heartbeat()
                    last_heartbeat = time.time()

                if line.startswith("data: "):
                    data_str = line[6:]
                    try:
                        data = json.loads(data_str)
                        if data.get("type") == "connected":
                            print(f"[INFO] Stream confirmed: {data}")
                            continue
                        # This is a task!
                        execute_task(data)
                    except json.JSONDecodeError:
                        pass
                elif line == ": ping":
                    # Keepalive, send heartbeat too
                    if time.time() - last_heartbeat > 120:
                        send_heartbeat()
                        last_heartbeat = time.time()

        except KeyboardInterrupt:
            print("\n[INFO] Shutting down...")
            break
        except Exception as e:
            print(f"[WARN] Connection lost: {e}")
            print("[INFO] Reconnecting in 5s...")
            time.sleep(5)


if __name__ == "__main__":
    print("=" * 60)
    print("  CC Local Listener")
    print("  Ctrl+C to stop")
    print("=" * 60)
    listen()
