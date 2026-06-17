#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/var/www/projector_project}"
ZIP_PATH="${ZIP_PATH:-/home/judy/projector_web_deploy.zip}"
BACKUP_ROOT="${BACKUP_ROOT:-/var/www}"
TMP_DIR="${TMP_DIR:-/tmp/projector_deploy}"
SERVICE_PATTERN="${SERVICE_PATTERN:-backend_server.py}"

if [ ! -f "$ZIP_PATH" ]; then
  echo "Deploy zip not found: $ZIP_PATH"
  exit 1
fi

if ! command -v unzip >/dev/null 2>&1; then
  echo "Missing unzip. Install it first: sudo apt install -y unzip"
  exit 1
fi

if ! command -v rsync >/dev/null 2>&1; then
  echo "Missing rsync. Install it first: sudo apt install -y rsync"
  exit 1
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$BACKUP_ROOT/projector_project_backup_$STAMP"

echo "[1/6] Backing up current app to $BACKUP_DIR"
if [ -d "$APP_DIR" ]; then
  sudo cp -a "$APP_DIR" "$BACKUP_DIR"
else
  sudo mkdir -p "$APP_DIR"
fi

echo "[2/6] Unpacking $ZIP_PATH"
rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"
unzip -q "$ZIP_PATH" -d "$TMP_DIR"

echo "[3/6] Syncing files to $APP_DIR"
sudo rsync -a --delete \
  --exclude 'venv/' \
  --exclude '.venv/' \
  --exclude 'nohup.out' \
  --exclude 'news.env' \
  --exclude 'news_collector.log' \
  "$TMP_DIR/" "$APP_DIR/"

echo "[4/6] Preparing Python environment"
cd "$APP_DIR"
if [ ! -x "venv/bin/python" ]; then
  python3 -m venv venv
fi

source venv/bin/activate
if [ -f "requirements.txt" ]; then
  if [ -d "packages" ]; then
    pip install --no-index --find-links=./packages -r requirements.txt
  else
    pip install -r requirements.txt
  fi
fi

chmod +x run_news_update.sh setup_news_cron.sh
bash setup_news_cron.sh

echo "[5/6] Restarting backend"
pkill -f "$SERVICE_PATTERN" || true
nohup python backend_server.py > nohup.out 2>&1 &
sleep 2

echo "Running initial projector news update"
if ! python news_collector.py --days 7 --max-items 100; then
  echo "Initial news update did not fetch new items; daily cron remains installed."
fi

echo "[6/6] Checking API"
if curl -fsS http://127.0.0.1:8000/api/brands >/dev/null; then
  echo "Deploy complete. API is responding."
else
  echo "Deploy finished, but API check failed. Inspect: $APP_DIR/nohup.out"
  exit 1
fi
