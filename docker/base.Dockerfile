# 系统依赖层：LibreOffice / 字体 / build-essential 等，变更频率低。
# 本地：docker build -f docker/base.Dockerfile -t knowledge_platform-base:latest .
# CI：推 ghcr.io/<owner>/knowledge_platform-base:latest，供 backend.Dockerfile 作为 FROM。
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# apt：加重试/超时、关闭 pipeline、按 host 排队下载，减轻 deb.debian.org 502 与代理不稳定
# 国内若仍大量 502：构建时加 --build-arg USE_CN_MIRROR=1（改用 mirrors.aliyun.com）
ARG USE_CN_MIRROR=0
RUN set -eux; \
    printf '%s\n' \
      'Acquire::Retries "15";' \
      'Acquire::http::Timeout "120";' \
      'Acquire::https::Timeout "120";' \
      'Acquire::http::Pipeline-Depth "0";' \
      'Acquire::Queue-Mode "host";' \
      'Acquire::CompressionTypes::Order:: "gz";' \
      > /etc/apt/apt.conf.d/80-docker-build; \
    if [ "$USE_CN_MIRROR" = "1" ]; then \
      for f in /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list.d/*.sources /etc/apt/sources.list.d/*.list; do \
        [ -f "$f" ] || continue; \
        sed -i 's/deb.debian.org/mirrors.aliyun.com/g' "$f" || true; \
      done; \
    fi; \
    apt-get update; \
    apt-get install -y --no-install-recommends build-essential; \
    apt-get install -y --no-install-recommends fonts-noto-cjk; \
    apt-get install -y --no-install-recommends libreoffice xvfb; \
    apt-get install -y --no-install-recommends xauth; \
    rm -rf /var/lib/apt/lists/*
