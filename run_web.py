import os
import subprocess
import webbrowser
import threading
import time
import sys

PORT = 8000

def get_python_exe():
    """ 嘗試尋找合適的 Python 執行檔 """
    # 優先嘗試專案內的 .venv
    venv_python = os.path.join(os.getcwd(), ".venv", "Scripts", "python.exe")
    if os.path.exists(venv_python):
        return venv_python
    
    # 其次嘗試當前運行的 Python
    return sys.executable

def check_dependencies(python_exe):
    """ 檢查必要的套件是否已安裝 """
    try:
        subprocess.check_call([python_exe, "-c", "import flask, flask_cors"], 
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

def start_server():
    python_exe = get_python_exe()
    
    if not check_dependencies(python_exe):
        print(f"\n[錯誤] 找不到必要的套件 (Flask, Flask-Cors)。")
        print(f"請確保環境已安裝套件，或手動執行: {python_exe} -m pip install flask flask-cors\n")
        return

    cmd = [python_exe, "backend_server.py"]
    print(f"正在啟動後台伺服器: {' '.join(cmd)}")
    
    # 使用 subprocess.Popen 以免阻塞
    try:
        process = subprocess.Popen(cmd)
        process.wait()
    except Exception as e:
        print(f"伺服器啟動失敗: {e}")

if __name__ == "__main__":
    # 在背景啟動伺服器
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    print("正在準備啟動網頁，請稍候...")
    
    # 稍等一下確保伺服器啟動
    time.sleep(3)
    
    # 自動打開瀏覽器
    print("正在開啟網頁...")
    webbrowser.open(f"http://localhost:{PORT}/index.html")
    
    print("\n-------------------------------------------")
    print(f"網頁已啟動:")
    print(f"前台網誌: http://localhost:{PORT}/index.html")
    print(f"管理後台: http://localhost:{PORT}/admin.html")
    print("密碼預設為: r6337856")
    print("-------------------------------------------\n")
    print("提示: 若看見 '拒絕連線'，請稍等 1-2 秒後重新整理網頁。")
    print("按 Ctrl+C 可以關閉伺服器。")

    # 保持主執行緒運行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在關閉伺服器...")
