# 交易机器人 + 控制面板共用镜像（启动命令由 docker-compose 指定）
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config ./config
COPY src ./src
COPY run_dashboard.py .

RUN addgroup --system app && adduser --system --ingroup app app \
    && mkdir -p /app/logs /app/tmp \
    && chown -R app:app /app

USER app

# 工作目录必须为项目根：ConfigLoader、.env、日志路径均相对此处
CMD ["python", "src/main.py"]
