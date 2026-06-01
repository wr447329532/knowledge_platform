# 应用层：依赖 base 中的 apt 包；代码与 pip 变更时只重建本阶段。
# 本地需先有基础镜像：docker build -f docker/base.Dockerfile -t knowledge_platform-base:latest .
# CI：BASE_IMAGE 指向 ghcr.io/<owner>/knowledge_platform-base:latest
ARG BASE_IMAGE=knowledge_platform-base:latest
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

ARG USE_CN_MIRROR=0

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

RUN chmod +x /app/docker/entrypoint.sh \
    && useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
