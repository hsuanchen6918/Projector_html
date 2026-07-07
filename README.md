#投影機競品網頁新版
#1/30新增SWQE競品標籤
#3/6新增後台管理頁面、比較機型頁面、後台管理新增建立新品牌


#從本地端bash上傳到VM 的指令
scp -r C:\Users\judy.chen\Desktop\projector_web.zip judy@192.168.202.35:/var/www/projector_project

#進入VM解壓縮
unzip projector_web.zip

#在VM將檔案傳至特定資料夾裡
mv projector_web.zip /home/judy/projector_project


#進入專案資料夾
cd /var/www/projector_project

#確保在虛擬環境中 (如果還沒建立過，請執行python3 -m venv venv)  ##資料夾前面會出現(venv)

#進入虛擬環境
source venv/bin/activate

#安裝flask
pip install --no-index --find-links=./packages flask flask-cors

#啟動後端伺服器
python backend_server.py

#開啟瀏覽器輸入http://[IP_ADDRESS]/index.html


#檢查 Nginx 設定檔
sudo cat /etc/nginx/sites-available/projector
#root /var/www/projector_project;
#index index.html;


#-------常用指令------------------------------


#刪除VM檔案
rm -rf projector_web.zip

#回到VM目錄 
cd ~
cd /home/judy

#取消(venv)環境指令
deactivate

#查詢VM資料夾
ls

#找出目前網頁「啟動中」的設定檔
ls -l /etc/nginx/sites-enabled/


#刪除VM特定資料夾裡所有檔案
rm -rf /home/judy/projector_web/*

#從設定檔中抓出root路徑
sudo grep "root" /etc/nginx/sites-available/projector



#查詢VM檔案在哪
find / -name "projector_web.zip"





## 從 VM 下載最新專案資料夾到本機

用途：如果 VM 上的 `/var/www/projector_project` 已經有最新投影機資料或最新網站內容，可以先把 VM 版本完整下載到本機備份資料夾，避免直接覆蓋目前本機專案。

建議下載到桌面的備份資料夾：

```powershell
scp -r judy@192.168.202.35:/var/www/projector_project "$env:USERPROFILE\Desktop\projector_project_vm_backup_$(Get-Date -Format yyyyMMdd_HHmmss)"
```

如果檔案很多，建議先在 VM 壓縮再下載：

```powershell
ssh judy@192.168.202.35 "cd /var/www && tar -czf /home/judy/projector_project_vm_backup.tar.gz projector_project"
scp judy@192.168.202.35:/home/judy/projector_project_vm_backup.tar.gz "$env:USERPROFILE\Desktop\projector_project_vm_backup.tar.gz"
tar -xzf "$env:USERPROFILE\Desktop\projector_project_vm_backup.tar.gz" -C "$env:USERPROFILE\Desktop"
```

注意：不要直接下載覆蓋 `C:\Users\judy.chen\Desktop\projector_project`，先放到另一個資料夾比較安全。確認 VM 資料正確後，再手動比對需要保留或合併的檔案。

## 後台一鍵下載所有投影機 JSON

用途：如果 VM 上的投影機資料比 GitHub 或本機新，可以先進入後台下載目前 VM 上所有 `data_*.json`，避免一個品牌一個品牌手動下載。

操作方式：

```text
1. 開啟後台: http://VM_IP:8000/admin.html
2. 輸入管理密碼登入
3. 點左側「下載全部投影機 JSON」
4. 瀏覽器會下載 projector_data_json_YYYYMMDD_HHMMSS.zip
```

ZIP 內容只包含 `data_*.json` 投影機資料檔，不包含圖片、PDF、新聞資料或其他網站程式碼。

## 後台一鍵下載 GitHub 同步包

用途：VM 後台新增機台後，除了 `data_*.json`，也可能新增圖片與開箱 PDF。後台可直接下載完整 GitHub 同步包。

操作方式：

```text
1. 開啟後台: http://VM_IP:8000/admin.html
2. 輸入管理密碼登入
3. 點左側「下載 GitHub 同步包」
4. 瀏覽器會下載 projector_github_sync_bundle_YYYYMMDD_HHMMSS.zip
```

ZIP 內容：

```text
data_*.json
images/
pptx/
projector_data_manifest.json
```

下載後解壓到本機專案，再 commit/push 到 GitHub。

## 從 VM 同步資料、圖片、PDF 到本機

用途：VM 後台新增機台後，除了 `data_*.json`，也可能新增圖片與開箱 PDF。要讓 GitHub Pages 也顯示完整內容，需要把三類資料都同步回本機後再 commit/push。

一鍵同步：

```powershell
cd C:\Users\judy.chen\Desktop\projector_project
powershell -ExecutionPolicy Bypass -File .\sync_vm_to_local.ps1 -VmHost 192.168.202.35 -VmUser judy -RemoteAppDir /var/www/projector_project
```

同步內容：

```text
data_*.json
images/
pptx/
projector_data_manifest.json
```

注意：這個同步只會下載或覆蓋同名檔案，不會刪除本機多出來的圖片或 PDF。確認內容正確後再提交 GitHub：

```powershell
git status
git add data_*.json images pptx projector_data_manifest.json
git commit -m "Sync projector data and media from VM"
git push origin main
```

## 中文檔名上傳規則

後台上傳圖片或 PDF 時，系統會自動把實體檔名改成 ASCII 安全檔名，例如：

```text
pptx_20260706_153000_ab12cd34.pdf
image_20260706_153000_ab12cd34.png
```

原因：VM 是 Linux、管理員可能從 Windows 或外部網路上傳檔案，中文檔名在瀏覽器、代理伺服器、SSH、壓縮/解壓縮之間可能發生編碼不一致，造成 `ls pptx` 或下載後檔名亂碼。

注意事項：

```text
1. 新上傳檔案會使用安全檔名，不再使用中文實體檔名。
2. 後台會自動把資料欄位更新成安全檔名或安全路徑。
3. 已經存在的亂碼檔名無法可靠自動還原原始中文，建議重新上傳原始檔，或手動改名後同步修正 data_*.json 裡的 PPTX / Image URL 欄位。
```

## 後台正常但下載後檔名亂碼

後台看到的檔名通常來自 `data_*.json` 裡的 `PPTX` 或 `Image URL` 欄位；下載專案資料夾時看到的檔名，則是檔案系統中的實體檔名。兩者不是同一件事。

如果後台顯示正常，但下載到 Windows 後檔名變亂碼，常見原因是壓縮/解壓工具把 Linux UTF-8 檔名用錯誤編碼解讀。

建議優先用 `scp -r` 直接下載資料夾，不要先壓縮：

```powershell
scp -r judy@192.168.202.35:/var/www/projector_project/images "$env:USERPROFILE\Desktop\projector_images_backup"
scp -r judy@192.168.202.35:/var/www/projector_project/pptx "$env:USERPROFILE\Desktop\projector_pptx_backup"
```

如果一定要壓縮，建議在 VM 用 Python 建立 UTF-8 ZIP：

```powershell
ssh judy@192.168.202.35 "cd /var/www/projector_project && python3 -m zipfile -c /home/judy/projector_media_utf8.zip images pptx"
scp judy@192.168.202.35:/home/judy/projector_media_utf8.zip "$env:USERPROFILE\Desktop\projector_media_utf8.zip"
```

下載後建議用 7-Zip 或 Windows 檔案總管解壓；不要用不支援 UTF-8 檔名的舊版壓縮工具。

若要判斷 VM 上實體檔名是否本來就已經亂碼，可在 VM 執行：

```bash
cd /var/www/projector_project
python3 - <<'PY'
import os
for folder in ("images", "pptx"):
    print(f"== {folder} ==")
    for name in os.listdir(folder):
        print(repr(name))
PY
```

如果這裡看到的檔名已經是亂碼，表示檔案在 VM 上就已經是亂碼，只能重新上傳原始檔或手動改名後修正對應的 `data_*.json` 欄位。


