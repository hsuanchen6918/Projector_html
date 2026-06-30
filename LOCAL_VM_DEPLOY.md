# 本機自動部署到 VM

適用情境：VM 只能在公司內網使用，不能連外抓新聞；改由本機先抓好新聞，再自動打包並部署到 VM。

## 流程

```text
Windows 本機
  -> 執行 news_collector.py 抓新聞
  -> 更新 news_data.json
  -> build_deploy_zip.ps1 打包
  -> scp 上傳 projector_web_deploy.zip 到 VM
  -> ssh 執行 VM 的 deploy_projector.sh
  -> VM 內部網站顯示最新每日焦點
```

## 手動執行一次

```powershell
cd C:\Users\judy.chen\Desktop\projector_project
powershell -ExecutionPolicy Bypass -File .\deploy_to_vm_from_local.ps1 -VmHost 192.168.202.35 -VmUser judy
```

若使用 SSH key：

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy_to_vm_from_local.ps1 `
  -VmHost 192.168.202.35 `
  -VmUser judy `
  -IdentityFile "$env:USERPROFILE\.ssh\projector_vm_ed25519"
```

## 建立每日本機排程

預設每天 Windows 本機時間 `09:00` 執行：

```powershell
cd C:\Users\judy.chen\Desktop\projector_project
powershell -ExecutionPolicy Bypass -File .\setup_local_vm_deploy_task.ps1 -VmHost 192.168.202.35 -VmUser judy
```

指定其他時間：

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_local_vm_deploy_task.ps1 `
  -VmHost 192.168.202.35 `
  -VmUser judy `
  -DailyTime 09:30
```

## 注意事項

- 本機必須能連外抓新聞，也必須能連到 VM。
- Windows 需安裝 OpenSSH Client，提供 `ssh` 與 `scp` 指令。
- 若排程要無人值守，建議使用 SSH key，不要依賴手動輸入密碼。
- VM 的 `deploy_projector.sh` 內含 `sudo`，若 sudo 需要密碼，排程會失敗；建議在 VM 上針對部署必要指令設定安全的免密 sudo，或改由有權限的部署帳號執行。
- `news.env` 不會被打包或上傳，避免 API key 或私密設定外流。
