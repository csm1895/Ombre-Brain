import os
import subprocess
import sys


LOG_PATH = os.environ.get("OMBRE_ZEABUR_CONTAINER_LOG_PATH", "/app/logs/zeabur_container.log")


def main() -> int:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8", buffering=1) as log_file:
        process = subprocess.Popen(
            [sys.executable, "-u", "server.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            log_file.write(line)
            log_file.flush()
        return process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
