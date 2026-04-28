FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

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
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

RUN chmod +x /app/docker/entrypoint.sh \
    && useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
