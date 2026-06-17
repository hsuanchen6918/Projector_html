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
python news_collector.py --days 7 --max-items 100
```

## 每日排程

部署腳本會自動執行：

```bash
bash setup_news_cron.sh
```

預設每天台北時間 `07:15` 執行。可用環境變數調整：

```bash
CRON_SCHEDULE="15 6 * * *" CRON_TIMEZONE="Asia/Taipei" bash setup_news_cron.sh
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
