import os
import subprocess
import sys
import time


LOG_PATH = os.environ.get("OMBRE_ZEABUR_CONTAINER_LOG_PATH", "/app/logs/zeabur_container.log")
TAILSCALE_PROXY = os.environ.get("OMBRE_TAILSCALE_PROXY", "http://127.0.0.1:1055")


def _log(log_file, line: str) -> None:
    sys.stdout.write(line)
    sys.stdout.flush()
    log_file.write(line)
    log_file.flush()


def _start_tailscale_if_configured(log_file) -> subprocess.Popen | None:
    auth_key = os.environ.get("TS_AUTHKEY") or os.environ.get("TAILSCALE_AUTHKEY")
    if not auth_key:
        _log(log_file, "[browser-mcp] Tailscale disabled: TS_AUTHKEY is not configured.\n")
        return None

    os.makedirs("/tmp/tailscale-state", exist_ok=True)
    tailscaled = subprocess.Popen(
        [
            "tailscaled",
            "--tun=userspace-networking",
            "--socks5-server=127.0.0.1:1055",
            "--outbound-http-proxy-listen=127.0.0.1:1055",
            "--statedir=/tmp/tailscale-state",
        ],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )
    time.sleep(2)
    up_cmd = [
        "tailscale",
        "up",
        f"--authkey={auth_key}",
        "--accept-routes",
        "--hostname=guyanshen-zeabur-browser-bridge",
    ]
    result = subprocess.run(up_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    _log(log_file, f"[browser-mcp] tailscale up exit={result.returncode}\n{result.stdout}\n")
    if result.returncode == 0:
        os.environ.setdefault("HTTP_PROXY", TAILSCALE_PROXY)
        os.environ.setdefault("http_proxy", TAILSCALE_PROXY)
        os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1,::1")
        os.environ.setdefault("no_proxy", "localhost,127.0.0.1,::1")
    return tailscaled


def main() -> int:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8", buffering=1) as log_file:
        tailscaled = _start_tailscale_if_configured(log_file)
        process = subprocess.Popen(
            [sys.executable, "-u", "server.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            _log(log_file, line)
        code = process.wait()
        if tailscaled is not None:
            tailscaled.terminate()
        return code


if __name__ == "__main__":
    raise SystemExit(main())
