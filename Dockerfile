# ============================================================
# Ombre Brain Docker Build
# Docker 构建文件
#
# Build: docker build -t ombre-brain .
# Run:   docker run -e OMBRE_API_KEY=your-key -p 8000:8000 ombre-brain
# ============================================================

FROM python:3.12-slim

WORKDIR /app

# Install Tailscale for optional browser MCP tailnet bridge.
# Uses userspace networking at runtime, so the app still starts without /dev/net/tun.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://tailscale.com/install.sh | sh \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first (leverage Docker cache)
# 先装依赖（利用 Docker 缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files / 复制项目文件
COPY *.py .
COPY ombre_mcp_readonly ./ombre_mcp_readonly
COPY config.example.yaml ./config.yaml
COPY buckets ./buckets

# Default to streamable-http for container (remote access)
# 容器场景默认用 streamable-http
ENV OMBRE_TRANSPORT=streamable-http
ENV OMBRE_CADENCE_DEEPSEEK_ENABLED=1

EXPOSE 8000

CMD ["python", "start_zeabur.py"]
