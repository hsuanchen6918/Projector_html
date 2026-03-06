import sys
import re
import time
import random
import requests
import datetime
import json
from bs4 import BeautifulSoup

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QFileDialog, QMessageBox, QLabel, QComboBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

BASE_DOMAIN = "https://www.projectorcentral.com"
BASE_LIST_URL = "https://www.projectorcentral.com/projectors.cfm?g=2&w_m=&mfg={brand}&pjl_m=&pjw_m=&pjh_m=&td_m=&is_m=&sort=date#list"

# 1. 在這裡新增你想要的欄位名稱
TARGET_FIELDS = [
    "Brand",
    "Model",
    "Image URL",
    "St. Price",
    "Released",
    "Brightness",
    "Resolution",
    "Contrast",
    "MEMC",
    "3D Modes",
    "Dolby Vision",
    "IMAX",
    "Flimmaker",
    "HDR10+",
    "Lamp Type",
    "Zoom Type",
    "Lens Shift",
    "DMD",
    "SoC",
    "Features",
    "Throw Ratio",
    "Screen Size",
    "Size (cm)",
    "System",
    "Weight (kg)",
    "Noise(dB(A))",
    "Power",
    "USB",
    "HDMI",
    "Wifi",
    "Typec",
    "3.5output",
    "Speakerpower",
    "Dolby Audio",
    "Audiocontrol",
    "Appcontrol",
    "AIscreen",
    "Autokeystone",
    "Autofocus",
    "Autofit",
    "Automove",
    "Eyesprotect",
    "Projectorstand",
    "Projectorhead",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
}


def clean_text(t: str) -> str:
    if not t: return "N/A"
    return re.sub(r"\s+", " ", t).strip()


def request_with_retry(url, max_retry=3, sleep_min=0.5, sleep_max=1.0):
    last_err = None
    for _ in range(max_retry):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=25)
            resp.raise_for_status()
            return resp
        except Exception as e:
            last_err = e
            time.sleep(sleep_min + random.random() * (sleep_max - sleep_min))
    raise last_err


def get_soup(url):
    r = request_with_retry(url)
    return BeautifulSoup(r.text, "html.parser")


def parse_brand_from_name(name: str) -> str:
    if not name: return "N/A"
    parts = name.split()
    return parts[0] if parts else "N/A"


def extract_pagination_urls(list_url):
    soup = get_soup(list_url)
    nav = soup.select_one("div.pageNav")
    pages = []
    if not nav: return pages
    anchors = nav.select("a")
    curr_idx = None
    for i, a in enumerate(anchors):
        if "curr" in a.get("class", []):
            curr_idx = i
            break
    candidates = anchors[1:3] if curr_idx is None else anchors[curr_idx + 1: curr_idx + 3]
    for a in candidates:
        href = a.get("href", "").strip()
        if not href: continue
        full = BASE_DOMAIN + href if href.startswith("/") else (
            href if href.startswith("http") else BASE_DOMAIN + "/" + href.lstrip("/")
        )
        pages.append(full)
    return pages


# 2. 修改此函式以抓取圖片 URL
def extract_model_links_from_list(list_url_or_urls):
    urls = list_url_or_urls if isinstance(list_url_or_urls, (list, tuple)) else [list_url_or_urls]
    links = []
    seen = set()

    for list_url in urls:
        try:
            soup = get_soup(list_url)
            # 1. 抓取所有包含型號連結的容器
            model_names = soup.select("div.modelName")
            print(f"\n--- 正在掃描列表頁，找到 {len(model_names)} 個型號 ---")

            for box in model_names:
                name_tag = box.select_one("a")
                if not name_tag: continue

                name = clean_text(name_tag.get_text(" ", strip=True))
                href = name_tag.get("href", "")
                full_url = BASE_DOMAIN + href if href.startswith("/") else href

                if full_url in seen: continue
                seen.add(full_url)

                # --- 核心偵錯邏輯：自動向上搜尋容器 ---
                img_url = "N/A"
                # 嘗試向上尋找可能包含圖片的父容器 (tr 或特定 div)
                container = box.find_parent(["tr", "div", "td"])

                # 如果找不到容器，就擴大範圍到整個網頁尋找 (備援方案)
                if container:
                    # 搜尋容器內所有圖片
                    all_imgs = container.find_all("img")
                    # 如果容器內沒圖片，再往上一層找
                    if not all_imgs:
                        container = container.parent
                        all_imgs = container.find_all("img") if container else []

                    for img in all_imgs:
                        src = img.get("src") or img.get("data-src") or ""
                        # 排除國旗 (flag)、評論星等 (star)、廣告、UI圖示
                        if "/images/" in src:
                            if any(k in src.lower() for k in ["flag", "star", "arrow", "spacer", "button"]):
                                continue

                            img_url = BASE_DOMAIN + src if src.startswith("/") else src
                            break  # 找到第一個看起來像投影機的圖就跳出

                brand = parse_brand_from_name(name)
                links.append({"name": name, "brand": brand, "url": full_url, "img": img_url})

                # 終端機偵錯輸出
                print(f"型號: {name[:20]} | 圖片狀態: {'成功' if img_url != 'N/A' else '失敗 (N/A)'}")
                if img_url != "N/A":
                    print(f"  └─ URL: {img_url}")

        except Exception as e:
            print(f"解析發生致命錯誤: {e}")

    return links


def find_by_labels(soup, labels):
    def norm(s: str) -> str:
        return clean_text(s).lower()

    exact = [norm(l) for l in labels]
    contain = [norm(l) for l in labels]

    def node_text(n):
        for tag in n.select("sup, label"): tag.decompose()
        return clean_text(n.get_text(" ", strip=True))

    # 特殊處理 Throw Ratio
    if "throw ratio" in exact:
        for span in soup.select("span"):
            if "throw ratio" in norm(span.get_text()):
                return node_text(span).replace("Throw Ratio", "(Optional Lense)")

    # 搜尋邏輯 (與原本一致)
    for tag_name in ["th", "dt", "dd"]:
        for tag in soup.find_all(tag_name):
            txt = norm(tag.get_text())
            if txt in exact or any(c in txt for c in contain):
                # 如果標籤本身就是標籤，找下一個內容
                if tag_name == "th": return node_text(tag.find_next("td"))
                if tag_name == "dt": return node_text(tag.find_next("dd"))
                if tag_name == "dd":
                    sib = tag.find_next_sibling()
                    return node_text(sib) if sib else "N/A"
    return "N/A"


# 規格標準化函式 (略，同前)
def normalize_focus_value(raw: str):
    t = clean_text(raw).lower()
    if any(k in t for k in ["powered", "motorized"]): return "Powered focus"
    return "Manual focus" if "focus" in t else "N/A"


def normalize_features_value(raw: str): return "Yes" if any(k in raw.lower() for k in ["google", "android"]) else "No"


def normalize_displaytype_value(raw: str):
    low = raw.lower()
    if "3lcd" in low: return "3LCD"
    if "dlp" in low: return "DLP"
    if "lcos" in low or "sxrd" in low: return raw # 保留高階技術名稱
    return raw if raw != "N/A" else "N/A"


# 3. 在這裡把圖片和新欄位存入 data
def parse_detail(url, preset_model=None, preset_brand=None, preset_img="N/A"):
    time.sleep(1.0)
    soup = get_soup(url)
    data = {k: "N/A" for k in TARGET_FIELDS}
    data["Detail URL"] = url
    data["Model"] = preset_model if preset_model else "N/A"
    data["Brand"] = preset_brand if preset_brand else parse_brand_from_name(data["Model"])
    data["Image URL"] = preset_img  # <--- 填入圖片

    # 基礎規格
    data["St. Price"] = find_by_labels(soup, ["Street Price"])
    data["Released"] = find_by_labels(soup, ["Released"])
    data["Brightness"] = find_by_labels(soup, ["White Brightness", "Brightness"])
    data["Resolution"] = find_by_labels(soup, ["Resolution"])
    data["Aspect Ratio"] = find_by_labels(soup,["Aspect Ratio"])
    data["Display Type"] = normalize_displaytype_value(find_by_labels(soup, ["Display Type"]))
    data["Lamp Type"] = find_by_labels(soup, ["Lamp Type"])
    data["Features"] = find_by_labels(soup, ["Features"])
    data["DMD"] = find_by_labels(soup, ["DMD", "DMD Chip"])
    data["Throw Ratio"] = find_by_labels(soup, ["Throw Ratio"])
    data["Lens Shift"] = find_by_labels(soup, ["Lens Shift"])
    data["Digital Zoom"] = find_by_labels(soup, ["Digital Zoom"])
    data["Digital Keystone"] = find_by_labels(soup, ["Digital Keystone"])
    data["Size (cm)"] = find_by_labels(soup, ["Projector Size", "WxHxD"])
    data["Weight (kg)"] = find_by_labels(soup, ["Weight"])
    data["3D Modes"] = find_by_labels(soup, ["3D Modes"])
    data["Noise(dB(A))"] = find_by_labels(soup, ["Audible Noise"])

    # 4. 這裡示範如何抓取原本沒有的新規格
    data["Contrast"] = find_by_labels(soup, ["Contrast", "Dynamic Contrast"])

    return data


# --- 以下類別 (Worker, App) 邏輯與前述相同，僅在呼叫 parse_detail 時傳入 m['img'] ---

import os 

# ... (existing imports)

# helper function for downloading images
def download_image(url, model_name):
    if not url or url == "N/A":
        return "N/A"
    
    # Create images directory if not exists
    if not os.path.exists("images"):
        os.makedirs("images")
        
    try:
        # Sanitize filename
        safe_name = re.sub(r'[\\/*?:"<>|]', "", model_name).replace(" ", "_")
        ext = url.split(".")[-1].split("?")[0]
        if len(ext) > 4 or not ext: ext = "jpg" # default fallback
        
        filename = f"images/{safe_name}.{ext}"
        
        # Check if file already exists to skip download
        if os.path.exists(filename):
            return filename
            
        # Download
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            with open(filename, 'wb') as f:
                f.write(r.content)
            return filename
        else:
            return "N/A"
    except Exception as e:
        print(f"Download failed for {model_name}: {e}")
        return "N/A"

# ... (rest of the file until Worker class)

class Worker(QThread):
    progress = pyqtSignal(str)
    row_parsed = pyqtSignal(dict)
    finished = pyqtSignal(list)

    def __init__(self, brand):
        super().__init__();
        self.brand = brand

    def run(self):
        rows = []
        try:
            list_url = BASE_LIST_URL.format(brand=self.brand)
            all_urls = [list_url] + extract_pagination_urls(list_url)
            model_links = extract_model_links_from_list(all_urls)

            for i, m in enumerate(model_links, 1):
                self.progress.emit(f"[{i}/{len(model_links)}] {m['name']}")
                
                # 自動下載圖片並更新路徑
                local_img_path = download_image(m['img'], m['name'])
                
                # 這裡傳入圖片網址 (現在是本地路徑)
                row = parse_detail(m["url"], m["name"], m["brand"], local_img_path)
                rows.append(row);
                self.row_parsed.emit(row)
            self.finished.emit(rows)
        except Exception as e:
            print(f"Worker Error: {e}")
            self.finished.emit(rows)


# ... (App 類別與 main 函數請保留你原本的寫法，只需確保 on_finished 裡有 json.dump 即可) ...


class App(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ProjectorCentral 擷取器")
        self.resize(1200, 680)

        layout = QVBoxLayout(self)

        brand_layout = QHBoxLayout()
        brand_label = QLabel("選擇品牌:")
        self.brand_combo = QComboBox()
        active_brands = [
            "Epson", "XGIMI", "JMGO", "Hisense", "BenQ", "ViewSonic", "Acer", "LG", "Samsung", "Dangbei"
        ]
        self.brand_combo.clear()
        self.brand_combo.addItems(active_brands)
        brand_layout.addWidget(brand_label)
        brand_layout.addWidget(self.brand_combo)
        brand_layout.addStretch(1)
        layout.addLayout(brand_layout)

        top_bar = QHBoxLayout()
        self.status_label = QLabel("待命")
        self.btn_start = QPushButton("開始擷取")
        self.btn_copy = QPushButton("複製選取列")
        top_bar.addWidget(self.status_label, stretch=1)
        top_bar.addWidget(self.btn_start)
        top_bar.addWidget(self.btn_export)
        top_bar.addWidget(self.btn_copy)

        layout.addLayout(top_bar)

        self.table = QTableWidget(0, len(TARGET_FIELDS))
        self.table.setHorizontalHeaderLabels(TARGET_FIELDS)
        self.table.setSelectionBehavior(self.table.SelectRows)
        self.table.setEditTriggers(self.table.NoEditTriggers)
        self.table.setAlternatingRowColors(True)

        column_widths = {
            "Brand": 80, "Model": 180, "St. Price": 80, "Released": 120,
            "Brightness": 120, "Resolution": 120, "Display Type": 80,
            "Light Source": 100, "DMD": 40, "Throw Ratio": 120,
            "Zoom Ratio": 120, "Auto Focus": 100, "Auto Keystone": 100,
            "Smart": 60, "Size (cm)": 140, "Weight (kg)": 80,
            "Noise(dB(A))": 100, "Detail URL": 200,
        }

        for i, field in enumerate(TARGET_FIELDS):
            width = column_widths.get(field, 100)
            self.table.setColumnWidth(i, width)

        layout.addWidget(self.table)

        self.btn_start.clicked.connect(self.on_start)
        self.btn_export.clicked.connect(self.on_export)
        self.btn_copy.clicked.connect(self.on_copy)

        self.rows = []
        self.worker = None

    def on_start(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "訊息", "擷取進行中，請稍候。")
            return

        selected_brand = self.brand_combo.currentText()
        self.rows = []
        self.table.setRowCount(0)
        self.status_label.setText(f"開始擷取 {selected_brand} 品牌資料...")

        self.worker = Worker(selected_brand)
        self.worker.progress.connect(self.on_progress)
        self.worker.row_parsed.connect(self.on_row_parsed)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_progress(self, msg):
        self.status_label.setText(msg)

    def on_row_parsed(self, row):
        self.rows.append(row)
        r = self.table.rowCount()
        self.table.insertRow(r)
        for c, key in enumerate(TARGET_FIELDS):
            self.table.setItem(r, c, QTableWidgetItem(row.get(key, "N/A")))

    # --- 這裡是你要求的修改核心處 ---
    def on_finished(self, rows):
        self.status_label.setText(f"完成，共 {len(rows)} 筆。")

        if not rows:
            return

        # 自動儲存 JSON 供網頁使用
        selected_brand = self.brand_combo.currentText().lower()
        json_filename = f"data_{selected_brand}.json"

        try:
            # --- 新增：合併邏輯，保留手動更新的欄位 ---
            existing_data = []
            if os.path.exists(json_filename):
                try:
                    with open(json_filename, "r", encoding="utf-8") as f:
                        existing_data = json.load(f)
                except:
                    pass
            
            # 建立現有資料的索引 (以 Model 為 key)
            existing_map = {item.get("Model"): item for item in existing_data if item.get("Model")}
            
            # 合併新舊資料
            merged_rows = []
            for new_item in rows:
                model_name = new_item.get("Model")
                if model_name in existing_map:
                    # 如果型號已存在，把現有的手動欄位 (不屬於 TARGET_FIELDS 的) 併入新抓取的資料
                    old_item = existing_map[model_name]
                    for key, val in old_item.items():
                        # 如果是手動欄位 (不管是自訂的還是 IsSWQE)，只要新抓的沒這欄位，就保留舊的
                        if key not in new_item or (new_item[key] == "N/A" and val != "N/A"):
                            new_item[key] = val
                merged_rows.append(new_item)

            with open(json_filename, "w", encoding="utf-8") as f:
                json.dump(merged_rows, f, ensure_ascii=False, indent=4)
                
            print(f"網頁用數據已更新 (已保留手動欄位): {json_filename}")
            QMessageBox.information(self, "存檔成功",
                                    f"品牌 {selected_brand} 的資料已抓取完畢。\n已自動產出網頁專用 JSON：{json_filename}\n(原有的手動欄位如 IsSWQE 已自動保留)")
        except Exception as e:
            QMessageBox.warning(self, "JSON 存檔失敗", f"雖然抓取成功，但存成 JSON 時出錯：\n{str(e)}")

    def on_export(self):
        if not self.rows:
            QMessageBox.information(self, "訊息", "尚無資料可輸出。")
            return

        now = datetime.datetime.now()
        time_str = now.strftime("%Y%m%d%H%M")



    def on_copy(self):
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            QMessageBox.information(self, "訊息", "請先選取列。")
            return
        lines = []
        for idx in sel:
            r = idx.row()
            vals = [self.table.item(r, c).text() if self.table.item(r, c) else "" for c in
                    range(self.table.columnCount())]
            lines.append("\t".join(vals))
        QApplication.clipboard().setText("\n".join(lines))
        QMessageBox.information(self, "已複製", f"複製 {len(sel)} 列到剪貼簿（以 TAB 分隔）。")


def main():
    app = QApplication(sys.argv)
    win = App()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()