#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/var/www/projector_project}"
CRON_SCHEDULE="${CRON_SCHEDULE:-15 7 * * *}"
CRON_TIMEZONE="${CRON_TIMEZONE:-Asia/Taipei}"
LOG_PATH="${LOG_PATH:-$APP_DIR/news_collector.log}"
COMMAND="$CRON_SCHEDULE APP_DIR=$APP_DIR /usr/bin/env bash $APP_DIR/run_news_update.sh >> $LOG_PATH 2>&1"

CURRENT_CRON="$(crontab -l 2>/dev/null || true)"
FILTERED_CRON="$(printf '%s\n' "$CURRENT_CRON" | grep -v 'run_news_update.sh' | grep -v '^CRON_TZ=' || true)"

{
  printf 'CRON_TZ=%s\n' "$CRON_TIMEZONE"
  printf '%s\n' "$FILTERED_CRON"
  printf '%s\n' "$COMMAND"
} | sed '/^[[:space:]]*$/d' | crontab -

echo "Installed daily projector news update:"
echo "Timezone: $CRON_TIMEZONE"
echo "$COMMAND"
