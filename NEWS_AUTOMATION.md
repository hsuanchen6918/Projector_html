# 每日焦點自動更新

## 資料流程

1. `news_collector.py` 讀取 `news_sources.json`
2. 抓取台灣、中國、美國、日本與官方消息 RSS
3. 過濾投影機、面板、DLP/DMD、3LCD、LCoS、光機及光源技術內容
4. 依標題與網址去重並標記國家、品牌、技術主題
5. 寫入 `news_data.json`，由網站「每日焦點」分頁顯示

## 手動執行

```bash
cd /var/www/projector_project
source venv/bin/activate
python news_collector.py --days 7 --max-items 1000 --retention-days 370
```

## 每日排程

### VM / Linux Cron

部署腳本會自動執行：

```bash
bash setup_news_cron.sh
```

預設每天台北時間 `09:00` 執行。可用環境變數調整：

```bash
CRON_SCHEDULE="0 8 * * *" CRON_TIMEZONE="Asia/Taipei" bash setup_news_cron.sh
```

## AI 繁中摘要

未設定 OpenAI 時，系統使用 RSS 內容產生基本摘要。要啟用翻譯與技術重點整理，請在執行排程的環境設定：

```bash
export AI_MODE=openai
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="gpt-4o-mini"
```

將 `news.env.example` 複製為不納入 Git 的 `news.env` 並填入設定。`run_news_update.sh` 會在每次執行前自動載入它：

```bash
cp news.env.example news.env
chmod 600 news.env
```

不要把 API Key 寫進 Git。

### GitHub Pages / GitHub Actions

GitHub Pages 不會執行 Python 或 Flask，因此使用 `.github/workflows/update-news.yml` 每天自動更新靜態資料。

GitHub Actions cron 使用 UTC；目前設定為：

```yaml
cron: "0 1 * * *"
```

也就是台北時間每天 `09:00`。流程如下：

1. Checkout repository
2. 使用 Python 3.12 執行 `news_collector.py`
3. 更新 `news_data.json`
4. 若內容有變更，自動 commit 並 push 回 `main`

GitHub Pages 會讀取更新後的 `news_data.json` 顯示每日焦點。

## 回補 2026 年歷史新聞

若要補抓 2026 年初到目前的新聞，可執行：

```bash
python news_collector.py --from-date 2026-01-01 --to-date 2026-06-18 --max-items 1000 --retention-days 370
```

`--to-date` 是不包含該日的結束日期。平常每日排程會保留約 370 天資料，因此回補進來的 2026 年新聞不會在隔天被清掉。
