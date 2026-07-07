# 本機抓新聞並部署到 VM

這套流程適合 VM 只能連公司內部網域、不能連外抓新聞的情境。

核心概念：

```text
Windows 本機
  -> 執行 news_collector.py 抓取外部新聞
  -> 產生或更新 news_data.json
  -> build_deploy_zip.ps1 只打包每日焦點相關檔案
  -> scp 上傳 projector_web_deploy.zip 到 VM
  -> scp 上傳最新版 deploy_projector.sh 到 VM
  -> ssh 執行 VM 部署腳本
  -> 只更新 /var/www/projector_project 內的每日焦點檔案
  -> VM 只顯示已部署的 news_data.json，不需要連外抓新聞
```

## 手動部署一次

```powershell
cd C:\Users\judy.chen\Desktop\projector_project
powershell -ExecutionPolicy Bypass -File .\deploy_to_vm_from_local.ps1 -VmHost 192.168.202.35 -VmUser judy -RemoteAppDir /var/www/projector_project -DailyFocusOnly
```

預設路徑：

```text
VM ZIP 路徑: /home/judy/projector_web_deploy.zip
VM 部署腳本: /home/judy/deploy_projector.sh
網站目錄: /var/www/projector_project
```

如果你有 SSH key：

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy_to_vm_from_local.ps1 `
  -VmHost 192.168.202.35 `
  -VmUser judy `
  -RemoteAppDir /var/www/projector_project `
  -DailyFocusOnly `
  -IdentityFile "$env:USERPROFILE\.ssh\projector_vm_ed25519"
```

## 安裝每日自動部署排程

每天早上 9 點在 Windows 本機抓新聞、打包並部署到 VM：

```powershell
cd C:\Users\judy.chen\Desktop\projector_project
powershell -ExecutionPolicy Bypass -File .\setup_local_vm_deploy_task.ps1 -VmHost 192.168.202.35 -VmUser judy -RemoteAppDir /var/www/projector_project
```

指定其他時間：

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_local_vm_deploy_task.ps1 `
  -VmHost 192.168.202.35 `
  -VmUser judy `
  -RemoteAppDir /var/www/projector_project `
  -DailyTime 09:30
```

## 注意事項

- 預設是「本機抓新聞，VM 不抓新聞」。這樣 VM 不能連外也能顯示每日焦點。
- 預設部署範圍是每日焦點，不會刪除 VM 上本機沒有的 `data_*.json` 投影機資料。
- 部署 ZIP 只會包含 `news_data.json`、`news_collector.py`、`news_sources.json`、`index.html`、`backend_server.py` 等每日焦點需要的檔案。
- VM 的 `deploy_projector.sh` 預設不會安裝 VM cron，也不會在 VM 端執行新聞抓取。
- 如果未來 VM 可以連外，才需要加上 `-EnableVmNewsFetch` 或 `-EnableVmNewsCron`。
- 如果確定要把本機專案完整覆蓋到 VM，才使用 `-FullProjectDeploy`。這會使用整站同步並可能刪除 VM 上本機沒有的檔案。
- Windows 本機需要 OpenSSH Client，也就是可以使用 `ssh` 和 `scp`。
- 若要排程全自動，建議設定 SSH key，避免每次部署都等待輸入密碼。
- 如果 VM 部署腳本需要 `sudo` 密碼，排程可能會卡住。建議設定只允許部署指令免密 sudo，或改由手動部署。

## VM 檢查指令

```bash
ls -l /home/judy/projector_web_deploy.zip
ls -l /home/judy/deploy_projector.sh
ls -l /var/www/projector_project/index.html
ls -l /var/www/projector_project/news_data.json
ls -l /var/www/projector_project/news_collector.py
sudo grep "root" /etc/nginx/sites-available/projector
```
