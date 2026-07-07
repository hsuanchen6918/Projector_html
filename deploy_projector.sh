#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/var/www/projector_project}"
ZIP_PATH="${ZIP_PATH:-/home/judy/projector_web_deploy.zip}"
BACKUP_ROOT="${BACKUP_ROOT:-/var/www}"
TMP_DIR="${TMP_DIR:-/tmp/projector_deploy}"
SERVICE_PATTERN="${SERVICE_PATTERN:-backend_server.py}"
ENABLE_VM_NEWS_FETCH="${ENABLE_VM_NEWS_FETCH:-0}"
ENABLE_VM_NEWS_CRON="${ENABLE_VM_NEWS_CRON:-0}"
DEPLOY_SCOPE="${DEPLOY_SCOPE:-daily-focus}"

if [ "$DEPLOY_SCOPE" != "daily-focus" ] && [ "$DEPLOY_SCOPE" != "full" ]; then
  echo "Invalid DEPLOY_SCOPE: $DEPLOY_SCOPE. Use daily-focus or full."
  exit 1
fi

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
sudo rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"
unzip -q "$ZIP_PATH" -d "$TMP_DIR"

echo "[3/6] Syncing files to $APP_DIR (scope: $DEPLOY_SCOPE)"
if [ "$DEPLOY_SCOPE" = "daily-focus" ]; then
  sudo mkdir -p "$APP_DIR"
  DAILY_FOCUS_FILES=(
    "index.html"
    "admin.html"
    "backend_server.py"
    "projector_data_manifest.json"
    "ai_client.py"
    "ai_engine.py"
    "news_collector.py"
    "news_sources.json"
    "news_data.json"
    "news.env.example"
    "NEWS_AUTOMATION.md"
    "LOCAL_VM_DEPLOY.md"
    "run_news_update.sh"
    "setup_news_cron.sh"
    "requirements.txt"
  )

  for relative_path in "${DAILY_FOCUS_FILES[@]}"; do
    if [ -f "$TMP_DIR/$relative_path" ]; then
      sudo rsync -a "$TMP_DIR/$relative_path" "$APP_DIR/$relative_path"
    else
      echo "Warning: $relative_path not found in deploy zip; skipped."
    fi
  done
else
  sudo rsync -a --delete \
    --exclude 'venv/' \
    --exclude '.venv/' \
    --exclude 'nohup.out' \
    --exclude 'news.env' \
    --exclude 'news_collector.log' \
    "$TMP_DIR/" "$APP_DIR/"
fi

sudo find "$APP_DIR" -type f -name '*.sh' -exec sed -i 's/\r$//' {} \;
sudo chown -R "$(id -un):$(id -gn)" "$APP_DIR"

echo "[4/6] Preparing Python environment"
cd "$APP_DIR"
if [ ! -x "venv/bin/python" ]; then
  python3 -m venv venv
fi

source venv/bin/activate
if [ -f "requirements.txt" ]; then
  if [ -d "packages" ]; then
    pip install --no-index --find-links=./packages -r requirements.txt
  elif [ "$DEPLOY_SCOPE" = "daily-focus" ]; then
    echo "Skipping pip install because packages/ is unavailable in Daily Focus deploy."
  else
    pip install -r requirements.txt
  fi
fi

if [ -f "run_news_update.sh" ]; then
  chmod +x run_news_update.sh
fi
if [ -f "setup_news_cron.sh" ]; then
  chmod +x setup_news_cron.sh
fi

if [ "$ENABLE_VM_NEWS_CRON" = "1" ]; then
  bash setup_news_cron.sh
else
  echo "Skipping VM news cron setup. News is expected to be collected locally before deploy."
fi

echo "[5/6] Restarting backend"
sudo pkill -f "$SERVICE_PATTERN" || true
rm -f nohup.out || sudo rm -f nohup.out
nohup python backend_server.py > nohup.out 2>&1 &
sleep 2

if [ "$ENABLE_VM_NEWS_FETCH" = "1" ]; then
  echo "Running initial projector news update on VM"
  if ! python news_collector.py --days 7 --max-items 2000 --retention-days 370; then
    echo "Initial news update did not fetch new items."
  fi
else
  if [ -f "news_data.json" ]; then
    echo "Skipping VM news fetch. Using deployed news_data.json."
  else
    echo "Warning: news_data.json is missing. Daily Focus will not show news until it is deployed."
  fi
fi

echo "[6/6] Checking API"
if curl -fsS http://127.0.0.1:8000/api/brands >/dev/null; then
  echo "Deploy complete. API is responding."
else
  echo "Deploy finished, but API check failed. Inspect: $APP_DIR/nohup.out"
  exit 1
fi
