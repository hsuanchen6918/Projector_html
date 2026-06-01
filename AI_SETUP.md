# AI 功能本機啟動方式

本專案目前保留兩種模式：

- `rules`：完全本地規則，不需要外網，適合公司內網部署。
- `openai`：本機開發時可連外，選機推薦會先用本地規則篩選，再呼叫 OpenAI 改寫推薦理由。

## 1. 本地規則模式

```powershell
python backend_server.py
```

打開：

```text
http://127.0.0.1:8000/index.html
```

## 2. 外部 AI 模式

在 VS Code Terminal 設定環境變數：

```powershell
$env:AI_MODE="openai"
$env:OPENAI_API_KEY="你的 OpenAI API key"
$env:OPENAI_MODEL="gpt-4o-mini"
python backend_server.py
```

## 3. 切回公司內網模式

```powershell
$env:AI_MODE="rules"
python backend_server.py
```

不設定 `AI_MODE` 時，預設就是 `rules`。

## 4. 目前功能分工

- 選機推薦：標籤點選後自動推薦；`openai` 模式會改寫推薦理由。
- 詳細規格差異：比較頁只顯示不同欄位，不呼叫 AI。
- 缺漏資料檢查：後台本地規則檢查，確保結果穩定可追蹤。
