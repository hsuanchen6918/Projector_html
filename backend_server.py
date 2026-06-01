from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
import re
import ai_engine
import ai_client

app = Flask(__name__)
CORS(app)

# 設定密碼
ADMIN_PASSWORD = "r6337856"
WORKING_DIR = os.path.dirname(os.path.abspath(__file__))


def unique_filename(directory, filename):
    name, ext = os.path.splitext(filename)
    candidate = filename
    counter = 1
    while os.path.exists(os.path.join(directory, candidate)):
        candidate = f"{name}_{counter}{ext}"
        counter += 1
    return candidate


def sanitize_upload_filename(filename):
    filename = os.path.basename(filename or "").strip()
    name, ext = os.path.splitext(filename)
    ext = ext.lower()
    name = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", "_", name)
    name = re.sub(r"\s+", "_", name).strip("._ ")
    if not name:
        name = "upload"
    return f"{name}{ext}"


def resolve_asset_file(root_dir, requested_path, fallback_exts=None):
    normalized = os.path.normpath(requested_path or "").replace("\\", os.sep)
    if normalized.startswith("..") or os.path.isabs(normalized):
        return None

    exact_path = os.path.abspath(os.path.join(root_dir, normalized))
    root_abs = os.path.abspath(root_dir)
    if not exact_path.startswith(root_abs + os.sep) and exact_path != root_abs:
        return None
    if os.path.isfile(exact_path):
        return exact_path

    current = root_abs
    parts = [part for part in normalized.split(os.sep) if part]
    for index, part in enumerate(parts):
        if not os.path.isdir(current):
            return None

        entries = os.listdir(current)
        lower_map = {entry.lower(): entry for entry in entries}
        match = lower_map.get(part.lower())

        if match:
            current = os.path.join(current, match)
            continue

        is_last = index == len(parts) - 1
        if is_last and fallback_exts:
            wanted_stem = os.path.splitext(part)[0].lower()
            for entry in entries:
                stem, ext = os.path.splitext(entry)
                if stem.lower() == wanted_stem and ext.lower() in fallback_exts:
                    candidate = os.path.join(current, entry)
                    if os.path.isfile(candidate):
                        return candidate
        return None

    return current if os.path.isfile(current) else None

@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    if response.mimetype in {"text/html", "text/css", "application/javascript"}:
        response.headers["Content-Type"] = f"{response.mimetype}; charset=utf-8"
    return response

@app.route('/')
def index():
    return send_from_directory(WORKING_DIR, 'index.html')

@app.route('/images/<path:filename>')
def image_files(filename):
    images_dir = os.path.join(WORKING_DIR, "images")
    resolved = resolve_asset_file(
        images_dir,
        filename,
        fallback_exts={".jpg", ".jpeg", ".png", ".webp", ".gif"},
    )
    if not resolved:
        return send_from_directory(WORKING_DIR, "assets/no-image.svg")
    return send_from_directory(os.path.dirname(resolved), os.path.basename(resolved))

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
    brands.sort()
    return jsonify(brands)

@app.route('/api/ai/tags', methods=['GET'])
def ai_tags():
    mode = "openai" if ai_client.openai_enabled() else "rules"
    return jsonify({"tags": ai_engine.tag_catalog(), "mode": mode})

@app.route('/api/ai/recommend', methods=['POST'])
def ai_recommend():
    data = request.json or {}
    tags = data.get('tags', [])
    swqe_only = bool(data.get('swqeOnly'))
    projectors = ai_engine.load_all_projectors(WORKING_DIR)
    if swqe_only:
        projectors = [p for p in projectors if p.get("IsSWQE") == "Yes"]
    result = ai_engine.recommend(projectors, tags)
    result["swqeOnly"] = swqe_only
    return jsonify(ai_client.enhance_recommendations(result))

@app.route('/api/ai/data-check', methods=['POST'])
def ai_data_check():
    token = request.headers.get('Authorization')
    if token != "Bearer dummy-token-123":
        return jsonify({"success": False, "message": "?芣?甈?"}), 403

    data = request.json or {}
    projectors = data.get('projectors', [])
    return jsonify(ai_engine.data_check(projectors, WORKING_DIR))

@app.route('/api/delete_brand', methods=['POST'])
def delete_brand():
    # 權限驗證
    token = request.headers.get('Authorization')
    if token != "Bearer dummy-token-123":
        return jsonify({"success": False, "message": "未授權"}), 403

    data = request.json
    brand = data.get('brand', '').lower()
    if not brand:
        return jsonify({"success": False, "message": "未提供品牌名稱"}), 400

    filename = f"data_{brand}.json"
    file_path = os.path.join(WORKING_DIR, filename)

    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return jsonify({"success": True, "message": f"品牌 {brand} 已成功刪除"})
        else:
            return jsonify({"success": False, "message": "找不到該品牌檔案"}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

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

@app.route('/api/upload', methods=['POST'])
def upload_file():
    # 權限驗證
    token = request.headers.get('Authorization')
    if token != "Bearer dummy-token-123":
        return jsonify({"success": False, "message": "未授權"}), 403

    if 'file' not in request.files:
        return jsonify({"success": False, "message": "未選擇檔案"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "message": "檔名不可為空"}), 400

    if file:
        upload_type = request.form.get('type', 'pptx')
        target_dir = 'images' if upload_type == 'image' else 'pptx'
        safe_name = sanitize_upload_filename(file.filename)
        if not safe_name:
            return jsonify({"success": False, "message": "檔名不合法"}), 400

        ext = os.path.splitext(safe_name)[1].lower()
        if upload_type == 'image' and ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            return jsonify({"success": False, "message": "圖片只支援 jpg、jpeg、png、webp、gif"}), 400
        if upload_type != 'image' and ext != ".pdf":
            return jsonify({"success": False, "message": "詳細開箱檔案只支援 PDF"}), 400
        
        save_dir = os.path.join(WORKING_DIR, target_dir)
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        safe_name = unique_filename(save_dir, safe_name)
        relative_path = f"{target_dir}/{safe_name}"
        
        file.save(os.path.join(save_dir, safe_name))
        return jsonify({
            "success": True,
            "message": f"檔案 {safe_name} 上傳成功",
            "filename": safe_name,
            "path": relative_path,
        })

if __name__ == '__main__':
    print(f"後台伺服器啟動於 http://0.0.0.0:8000")
    print(f"前台地址: http://[您的IP]:8000/index.html")
    print(f"後台地址: http://[您的IP]:8000/admin.html")
    app.run(host='0.0.0.0', port=8000, debug=True)
