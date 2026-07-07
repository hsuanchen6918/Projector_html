from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import datetime as dt
import io
import json
import os
import re
import subprocess
import sys
import uuid
import zipfile
import ai_engine
import ai_client

app = Flask(__name__)
CORS(app)

# 設定密碼
ADMIN_PASSWORD = "r6337856"
WORKING_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECTOR_MANIFEST_FILE = "projector_data_manifest.json"


def canonical_brand_key(value):
    key = str(value or "").strip().lower()
    key = re.sub(r"\s+", "", key)
    key = re.sub(r"[^a-z0-9_-]+", "", key)
    return key


def brand_key_from_filename(filename):
    lower_name = filename.lower()
    if not lower_name.startswith("data_") or not lower_name.endswith(".json"):
        return ""
    return canonical_brand_key(filename[5:-5])


def data_filename_for_brand(brand_key):
    return f"data_{brand_key}.json"


def projector_data_files():
    return sorted(
        filename for filename in os.listdir(WORKING_DIR)
        if filename.lower().startswith("data_")
        and filename.lower().endswith(".json")
        and os.path.isfile(os.path.join(WORKING_DIR, filename))
    )


def projector_data_files_for_brand(brand_key):
    return [
        filename for filename in projector_data_files()
        if brand_key_from_filename(filename) == brand_key
    ]


def projector_brands():
    brands = []
    for filename in projector_data_files():
        brand = brand_key_from_filename(filename)
        if brand:
            brands.append(brand)
    return sorted(set(brands))


def best_brand_label(labels, brand_key):
    if brand_key and len(brand_key) <= 3:
        return brand_key.upper()

    cleaned = [str(label).strip() for label in labels if str(label or "").strip()]
    if not cleaned:
        return brand_key.upper() if brand_key else ""

    counts = {}
    first_seen = {}
    for index, label in enumerate(cleaned):
        counts[label] = counts.get(label, 0) + 1
        first_seen.setdefault(label, index)

    def score(label):
        has_lower = any(char.islower() for char in label)
        has_upper = any(char.isupper() for char in label)
        if has_lower and has_upper:
            return 30
        if label == label.upper() and len(brand_key) <= 5:
            return 25
        if label == label.lower():
            return 5
        return 10

    return sorted(
        counts.keys(),
        key=lambda label: (counts[label], score(label), -first_seen[label]),
        reverse=True,
    )[0]


def read_brand_labels_from_file(filename):
    file_path = os.path.join(WORKING_DIR, filename)
    try:
        with open(file_path, "r", encoding="utf-8") as data_file:
            rows = json.load(data_file)
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(rows, list):
        return []
    return [
        row.get("Brand")
        for row in rows
        if isinstance(row, dict) and row.get("Brand")
    ]


def canonical_brand_display(brand_key, projectors=None, preferred_label=None):
    existing_labels = []
    for filename in projector_data_files_for_brand(brand_key):
        existing_labels.extend(read_brand_labels_from_file(filename))
    if existing_labels:
        return best_brand_label(existing_labels, brand_key)

    labels = []
    if preferred_label:
        labels.append(preferred_label)
    if isinstance(projectors, list):
        labels.extend(
            row.get("Brand")
            for row in projectors
            if isinstance(row, dict) and row.get("Brand")
        )
    return best_brand_label(labels, brand_key)


def write_projector_manifest():
    manifest_path = os.path.join(WORKING_DIR, PROJECTOR_MANIFEST_FILE)
    manifest = {
        "brands": projector_brands(),
    }
    with open(manifest_path, "w", encoding="utf-8") as manifest_file:
        json.dump(manifest, manifest_file, ensure_ascii=False, indent=2)


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


def safe_storage_filename(upload_type, original_filename):
    _, ext = os.path.splitext(original_filename or "")
    ext = ext.lower()
    prefix = "image" if upload_type == "image" else "pptx"
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}_{uuid.uuid4().hex[:8]}{ext}"


def add_folder_to_zip(zip_file, folder_name):
    folder_path = os.path.join(WORKING_DIR, folder_name)
    if not os.path.isdir(folder_path):
        return

    for current_dir, _, filenames in os.walk(folder_path):
        for filename in filenames:
            full_path = os.path.join(current_dir, filename)
            relative_path = os.path.relpath(full_path, WORKING_DIR).replace(os.sep, "/")
            zip_file.write(full_path, arcname=relative_path)


def send_zip_archive(archive, filename):
    archive.seek(0)
    return send_file(
        archive,
        mimetype="application/zip",
        as_attachment=True,
        download_name=filename,
    )


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
    return jsonify(projector_brands())

@app.route('/api/export_projector_data', methods=['GET'])
def export_projector_data():
    token = request.headers.get('Authorization')
    if token != "Bearer dummy-token-123":
        return jsonify({"success": False, "message": "未授權"}), 403

    data_files = projector_data_files()

    if not data_files:
        return jsonify({"success": False, "message": "沒有找到投影機 data_*.json 檔案"}), 404

    archive = io.BytesIO()
    with zipfile.ZipFile(archive, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for filename in data_files:
            zip_file.write(os.path.join(WORKING_DIR, filename), arcname=filename)

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return send_zip_archive(archive, f"projector_data_json_{timestamp}.zip")


@app.route('/api/export_projector_sync_bundle', methods=['GET'])
def export_projector_sync_bundle():
    token = request.headers.get('Authorization')
    if token != "Bearer dummy-token-123":
        return jsonify({"success": False, "message": "未授權"}), 403

    data_files = projector_data_files()
    if not data_files:
        return jsonify({"success": False, "message": "沒有找到投影機 data_*.json 檔案"}), 404

    write_projector_manifest()
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for filename in data_files:
            zip_file.write(os.path.join(WORKING_DIR, filename), arcname=filename)

        manifest_path = os.path.join(WORKING_DIR, PROJECTOR_MANIFEST_FILE)
        if os.path.isfile(manifest_path):
            zip_file.write(manifest_path, arcname=PROJECTOR_MANIFEST_FILE)

        add_folder_to_zip(zip_file, "images")
        add_folder_to_zip(zip_file, "pptx")

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return send_zip_archive(archive, f"projector_github_sync_bundle_{timestamp}.zip")

@app.route('/api/news', methods=['GET'])
def get_news():
    news_path = os.path.join(WORKING_DIR, "news_data.json")
    if not os.path.exists(news_path):
        return jsonify([])

    try:
        with open(news_path, "r", encoding="utf-8") as news_file:
            news_items = json.load(news_file)
        if not isinstance(news_items, list):
            return jsonify({"success": False, "message": "新聞資料格式錯誤"}), 500
        return jsonify(news_items)
    except (OSError, json.JSONDecodeError) as error:
        return jsonify({"success": False, "message": str(error)}), 500

@app.route('/api/news/refresh', methods=['POST'])
def refresh_news():
    token = request.headers.get('Authorization')
    if token != "Bearer dummy-token-123":
        return jsonify({"success": False, "message": "未授權"}), 403

    collector_path = os.path.join(WORKING_DIR, "news_collector.py")
    try:
        result = subprocess.run(
            [sys.executable, collector_path, "--days", "7", "--max-items", "100"],
            cwd=WORKING_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=180,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return jsonify({"success": False, "message": str(error)}), 500

    output = result.stdout.strip()
    try:
        details = json.loads(output) if output else {}
    except json.JSONDecodeError:
        details = {"output": output}
    if result.returncode not in {0, 1}:
        return jsonify({
            "success": False,
            "message": result.stderr.strip() or "新聞更新失敗",
            "details": details,
        }), 500
    return jsonify({"success": True, "details": details})

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

    data = request.json or {}
    brand = canonical_brand_key(data.get('brand', ''))
    if not brand:
        return jsonify({"success": False, "message": "未提供品牌名稱"}), 400

    try:
        filenames = projector_data_files_for_brand(brand)
        if not filenames:
            return jsonify({"success": False, "message": "Brand data file not found"}), 404

        for filename in filenames:
            os.remove(os.path.join(WORKING_DIR, filename))
        write_projector_manifest()
        return jsonify({"success": True, "message": f"Brand {brand} deleted"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/save', methods=['POST'])
def save_data():
    # 簡單的 token 驗證 (僅示意)
    token = request.headers.get('Authorization')
    if token != "Bearer dummy-token-123":
        return jsonify({"success": False, "message": "未授權"}), 403

    data = request.json or {}
    brand = canonical_brand_key(data.get('brand', ''))
    projectors = data.get('data', [])
    preferred_label = data.get('brandDisplay') or data.get('displayBrand') or data.get('brandLabel')

    if not brand:
        return jsonify({"success": False, "message": "Missing brand"}), 400
    if not isinstance(projectors, list):
        return jsonify({"success": False, "message": "Projector data must be a list"}), 400

    brand_display = canonical_brand_display(brand, projectors, preferred_label)
    normalized_projectors = []
    for projector in projectors:
        if not isinstance(projector, dict):
            continue
        normalized = dict(projector)
        normalized["Brand"] = brand_display
        normalized_projectors.append(normalized)

    filename = data_filename_for_brand(brand)
    file_path = os.path.join(WORKING_DIR, filename)

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(normalized_projectors, f, ensure_ascii=False, indent=4)

        expected_path = os.path.normcase(os.path.abspath(file_path))
        for variant_filename in projector_data_files_for_brand(brand):
            variant_path = os.path.join(WORKING_DIR, variant_filename)
            if os.path.normcase(os.path.abspath(variant_path)) != expected_path:
                os.remove(variant_path)

        write_projector_manifest()
        return jsonify({
            "success": True,
            "message": f"Saved {filename}",
            "brand": brand,
            "brandDisplay": brand_display,
        })
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
        original_name = sanitize_upload_filename(file.filename)
        if not original_name:
            return jsonify({"success": False, "message": "檔名不合法"}), 400

        ext = os.path.splitext(original_name)[1].lower()
        if upload_type == 'image' and ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            return jsonify({"success": False, "message": "圖片只支援 jpg、jpeg、png、webp、gif"}), 400
        if upload_type != 'image' and ext != ".pdf":
            return jsonify({"success": False, "message": "詳細開箱檔案只支援 PDF"}), 400
        
        save_dir = os.path.join(WORKING_DIR, target_dir)
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        safe_name = safe_storage_filename(upload_type, original_name)
        safe_name = unique_filename(save_dir, safe_name)
        relative_path = f"{target_dir}/{safe_name}"
        
        file.save(os.path.join(save_dir, safe_name))
        return jsonify({
            "success": True,
            "message": f"檔案已用安全檔名 {safe_name} 上傳成功",
            "filename": safe_name,
            "original_filename": original_name,
            "path": relative_path,
        })

if __name__ == '__main__':
    print(f"後台伺服器啟動於 http://0.0.0.0:8000")
    print(f"前台地址: http://[您的IP]:8000/index.html")
    print(f"後台地址: http://[您的IP]:8000/admin.html")
    app.run(host='0.0.0.0', port=8000, debug=True)
