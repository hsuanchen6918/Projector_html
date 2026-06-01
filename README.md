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







