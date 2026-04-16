#!/usr/bin/env bash
# 将项目同步到远程服务器并用 Docker Compose 启动（需在本地已可免密 SSH 登录）
#
# 用法:
#   chmod +x scripts/deploy.sh
#   ./scripts/deploy.sh ubuntu@43.155.205.34
#
# 可选环境变量:
#   REMOTE_DIR   远端项目目录，默认 /opt/ai-trading-bot
#
# 首次部署前请在服务器上:
#   1) 安装 Docker 与 Docker Compose 插件
#   2) 将本机 .env 拷到远端（勿把 .env 提交到 Git）:
#        scp .env ubuntu@43.155.205.34:/opt/ai-trading-bot/.env
#   3) 确保远端存在 config/trading_config.json（随 rsync 会带上）
#
set -euo pipefail

REMOTE="${1:-}"
if [[ -z "$REMOTE" ]]; then
  echo "用法: $0 <user@host>  例如: $0 ubuntu@43.155.205.34" >&2
  exit 1
fi

REMOTE_DIR="${REMOTE_DIR:-/opt/ai-trading-bot}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> 同步代码到 ${REMOTE}:${REMOTE_DIR}（不包含 .git / venv / 本机 .env）"
ssh -o BatchMode=yes "${REMOTE}" "mkdir -p '${REMOTE_DIR}'"
rsync -az \
  --exclude '.git/' \
  --exclude 'venv/' \
  --exclude 'env/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.env' \
  --exclude '.env.*' \
  --exclude 'logs/' \
  "${ROOT}/" "${REMOTE}:${REMOTE_DIR}/"

echo "==> 远端构建并启动 Docker Compose"
ssh -o BatchMode=yes "${REMOTE}" bash -s <<EOF
set -euo pipefail
cd '${REMOTE_DIR}'
mkdir -p logs
if [[ ! -f .env ]]; then
  echo "错误: 远端 ${REMOTE_DIR}/.env 不存在。请先执行: scp .env ${REMOTE}:${REMOTE_DIR}/.env" >&2
  exit 1
fi
docker compose build
docker compose up -d
docker compose ps
EOF

echo "==> 部署完成。Dashboard 端口见远端 .env 中 DASHBOARD_PUBLISH_PORT（默认映射 5000）。"
