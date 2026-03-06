from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os

app = Flask(__name__)
CORS(app)

# 設定密碼
ADMIN_PASSWORD = "r6337856"
WORKING_DIR = os.path.dirname(os.path.abspath(__file__))

@app.route('/')
def index():
    return send_from_directory(WORKING_DIR, 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(WORKING_DIR, path)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    if data.get('password') == ADMIN_PASSWORD:
        return jsonify({"success": True, "token": "dummy-token-123"})
    return jsonify({"success": False, "message": "密碼錯誤"}), 401

@app.route('/api/brands', methods=['GET'])
def get_brands():
    brands = []
    for filename in os.listdir(WORKING_DIR):
        if filename.startswith('data_') and filename.endswith('.json'):
            brand = filename[5:-5]
            if brand:
                brands.append(brand)
    return jsonify(brands)

@app.route('/api/save', methods=['POST'])
def save_data():
    # 簡單的 token 驗證 (僅示意)
    token = request.headers.get('Authorization')
    if token != "Bearer dummy-token-123":
        return jsonify({"success": False, "message": "未授權"}), 403

    data = request.json
    brand = data.get('brand', '').lower()
    projectors = data.get('data', [])

    if not brand:
        return jsonify({"success": False, "message": "未提供品牌名稱"}), 400

    filename = f"data_{brand}.json"
    file_path = os.path.join(WORKING_DIR, filename)

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(projectors, f, ensure_ascii=False, indent=4)
        return jsonify({"success": True, "message": f"成功儲存 {filename}"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

if __name__ == '__main__':
    print(f"後台伺服器啟動於 http://localhost:8000")
    print(f"前台地址: http://localhost:8000/index.html")
    print(f"後台地址: http://localhost:8000/admin.html")
    app.run(port=8000, debug=True)
