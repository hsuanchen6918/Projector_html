#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/var/www/projector_project}"
cd "$APP_DIR"

if [ -f "news.env" ]; then
  set -a
  source news.env
  set +a
fi

if [ -f "venv/bin/activate" ]; then
  source venv/bin/activate
fi

python news_collector.py --days 7 --max-items 1000 --retention-days 370
