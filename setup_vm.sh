#!/bin/bash

# Ubuntu 24.04 Server Setup Script for Projector Web (Static Mode)
# Purpose: Prepare the environment for a pure Nginx static deployment.

echo "=========================================="
echo "   PROJECTOR WEB - STATIC SETUP"
echo "=========================================="

# 1. Update system
echo "[1/2] 更新系統包表..."
sudo apt update

# 2. Install Nginx and Unzip
echo "[2/2] 安裝 Nginx 與 Unzip..."
sudo apt install -y nginx unzip

echo "=========================================="
echo "✅ 設定完成！"
echo "=========================================="
echo "部署建議："
echo "1. 將所有檔案放入 /var/www/html/ 即可直接瀏覽"
echo "2. 如果原本已有 Nginx 設定，請確保 root 指向正確資料夾"
echo "------------------------------------------"
echo "注意：離線模式下 Nginx 會處理所有靜態檔案讀取。"
echo "不需要執行 Python 或是啟動 backend_server.py。"
echo "=========================================="
