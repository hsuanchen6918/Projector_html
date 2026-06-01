import os
import re
from collections import Counter, defaultdict


MISSING_VALUES = {"", "-", "--", "?", "??", "N/A", "NA", "None", None}


TAG_RULES = [
    {"id": "4k", "label": "4K"},
    {"id": "ultra-short-throw", "label": "超短焦"},
    {"id": "low-noise", "label": "低噪音"},
    {"id": "lightweight", "label": "輕便"},
    {"id": "autofocus", "label": "自動對焦"},
    {"id": "autokeystone", "label": "自動梯形校正"},
    {"id": "ai-screen", "label": "自動對框"},
    {"id": "dolby-vision", "label": "Dolby Vision"},
    {"id": "hdr", "label": "HDR10+"},
    {"id": "memc", "label": "MEMC"},
    {"id": "laser", "label": "雷射光源"},
]


def is_missing(value):
    if value in MISSING_VALUES:
        return True
    if isinstance(value, str) and value.strip() in MISSING_VALUES:
        return True
    return False


def text(value):
    return "" if is_missing(value) else str(value)


def parse_number(value):
    if is_missing(value):
        return None
    match = re.search(r"(\d[\d,]*(?:\.\d+)?)", str(value))
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def has_yes(value):
    normalized = text(value).lower()
    return normalized in {"yes", "y", "true"} or "支援" in normalized or "auto" in normalized


def has_text(projector, fields, keywords):
    haystack = " ".join(text(projector.get(field)) for field in fields).lower()
    return any(keyword.lower() in haystack for keyword in keywords)


def is_4k(projector):
    return has_text(projector, ["Resolution", "Aspect Ratio", "Features"], ["3840", "2160", "4k", "uhd"])


def brightness(projector):
    return parse_number(projector.get("Brightness"))


def weight(projector):
    return parse_number(projector.get("Weight (kg)"))


def noise(projector):
    return parse_number(projector.get("Noise(dB(A))"))


def throw_ratio(projector):
    return parse_number(projector.get("Throw Ratio"))


def display_name(projector):
    brand = text(projector.get("Brand")).upper()
    model = text(projector.get("Model"))
    return f"{brand} {model}".strip()


def load_all_projectors(working_dir):
    import json

    projectors = []
    for filename in os.listdir(working_dir):
        if not filename.startswith("data_") or not filename.endswith(".json"):
            continue
        brand = filename[5:-5]
        path = os.path.join(working_dir, filename)
        try:
            with open(path, "r", encoding="utf-8") as file:
                rows = json.load(file)
        except Exception:
            continue
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict):
                item = dict(row)
                item["Brand"] = (text(item.get("Brand")) or brand).upper()
                projectors.append(item)
    return projectors


def tag_catalog():
    return TAG_RULES


def score_projector(projector, selected_tags):
    score = 0
    reasons = []
    cautions = []
    matched_tags = set()
    fields = ["Features", "System", "Lamp Type", "Resolution", "Throw Ratio"]

    def add(points, reason, tag_id=None):
        nonlocal score
        score += points
        reasons.append(reason)
        if tag_id:
            matched_tags.add(tag_id)

    def spec(field):
        return text(projector.get(field))

    tag_set = set(selected_tags or [])
    b = brightness(projector)
    w = weight(projector)
    n = noise(projector)
    tr = throw_ratio(projector)
    resolution = spec("Resolution")
    lamp_type = spec("Lamp Type")

    if "4k" in tag_set and is_4k(projector):
        add(18, f"解析度為 {resolution or '4K / UHD'}，符合高解析觀影需求", "4k")
    if "ultra-short-throw" in tag_set and tr and tr < 0.5:
        add(18, f"投射比約 {tr:g}，適合靠牆或小空間使用", "ultra-short-throw")
    if "low-noise" in tag_set and n and n <= 28:
        add(12, f"噪音約 {n:g} dB，適合需要安靜觀影或簡報的環境", "low-noise")
    if "lightweight" in tag_set and w and w <= 4:
        add(12, f"重量約 {w:g} kg，移動、收納或跨空間使用較方便", "lightweight")
    if "autofocus" in tag_set and has_yes(projector.get("Autofocus")):
        add(12, f"畫面能自動變清晰", "autofocus")
    if "autokeystone" in tag_set and not is_missing(projector.get("Autokeystone")):
        add(10, f"畫面能自動變為矩形", "autokeystone")
    if "ai-screen" in tag_set and has_yes(projector.get("AIscreen")):
        add(12, f"投影機能自動入幕", "ai-screen")
    if "dolby-vision" in tag_set and has_yes(projector.get("Dolby Vision")):
        add(12, f"適合重視電影HDR效果的使用者", "dolby-vision")
    if "hdr" in tag_set and has_yes(projector.get("HDR10+")):
        add(10, f"能支援較完整的高動態範圍片源", "hdr")
    if "memc" in tag_set and has_yes(projector.get("MEMC")):
        add(8, f"觀看運動、遊戲或快速畫面時較有幫助", "memc")
    if "laser" in tag_set and has_text(projector, ["Lamp Type"], ["laser", "RGB","激光"]):
        add(10, f"光源類型為 {lamp_type or '雷射'}，適合重視亮度穩定與長效光源的需求", "laser")

    if "high-brightness" in tag_set and not b:
        cautions.append("亮度資料缺漏，需補齊後再確認")
    if "low-noise" in tag_set and not n:
        cautions.append("噪音資料缺漏，無法判斷低噪音表現")
    if "lightweight" in tag_set and not w:
        cautions.append("重量資料缺漏，無法判斷攜帶性")

    return {
        "score": score,
        "matchedTags": sorted(matched_tags),
        "reasons": reasons[:5],
        "cautions": cautions[:3],
    }


def recommend(projectors, tags, limit=10):
    required_tags = set(tags or [])
    scored = []
    for projector in projectors:
        result = score_projector(projector, tags)
        if result["score"] <= 0:
            continue
        if required_tags and not required_tags.issubset(set(result.get("matchedTags", []))):
            continue
        scored.append({**result, "projector": projector})
    if "lightweight" in required_tags:
        scored.sort(key=lambda row: (
            weight(row["projector"]) is None,
            weight(row["projector"]) or float("inf"),
            -row["score"],
        ))
    elif "low-noise" in required_tags:
        scored.sort(key=lambda row: (
            noise(row["projector"]) is None,
            noise(row["projector"]) or float("inf"),
            -row["score"],
        ))
    else:
        scored.sort(key=lambda row: row["score"], reverse=True)
    return {
        "mode": "rules",
        "selectedTags": tags,
        "recommendations": scored[:limit],
        "totalMatches": len(scored),
        "displayLimit": limit,
        "message": "使用本地規則引擎產生推薦，未連接外部 AI 服務。",
    }


def data_check(projectors, working_dir):
    required = ["Brand", "Model", "St. Price", "Brightness", "Resolution", "Image URL"]
    ai_fields = ["AIscreen", "Autofocus", "Autokeystone", "Autofit", "Automove", "Eyesprotect"]
    issues = []
    model_counter = Counter(text(p.get("Model")).lower() for p in projectors if text(p.get("Model")))

    for idx, projector in enumerate(projectors):
        name = display_name(projector) or f"第 {idx + 1} 筆資料"
        for field in required:
            if is_missing(projector.get(field)):
                issues.append(_issue("critical", name, field, "必填欄位缺漏"))
        for field in ai_fields:
            if is_missing(projector.get(field)):
                issues.append(_issue("warning", name, field, "AI / 自動化功能欄位尚未填寫"))

        image_url = text(projector.get("Image URL"))
        if image_url.startswith("http://") or image_url.startswith("https://"):
            issues.append(_issue("warning", name, "Image URL", "圖片仍指向外部網址，內網可能無法顯示"))
        elif image_url and not os.path.exists(os.path.join(working_dir, image_url.replace("/", os.sep))):
            issues.append(_issue("warning", name, "Image URL", "本機圖片檔案不存在"))

        if projector.get("IsSWQE") == "Yes":
            pptx = text(projector.get("PPTX"))
            if not pptx:
                issues.append(_issue("critical", name, "PPTX", "SWQE 機型缺少開箱檔案欄位"))
            elif not os.path.exists(os.path.join(working_dir, "pptx", pptx)):
                issues.append(_issue("warning", name, "PPTX", "SWQE 開箱檔案不存在或檔名不一致"))

        model_key = text(projector.get("Model")).lower()
        if model_key and model_counter[model_key] > 1:
            issues.append(_issue("warning", name, "Model", "型號重複"))

        if parse_number(projector.get("Brightness")) is None and not is_missing(projector.get("Brightness")):
            issues.append(_issue("info", name, "Brightness", "亮度格式無法解析數字"))
        if parse_number(projector.get("Weight (kg)")) is None and not is_missing(projector.get("Weight (kg)")):
            issues.append(_issue("info", name, "Weight (kg)", "重量格式無法解析數字"))

    grouped = defaultdict(int)
    for issue in issues:
        grouped[issue["severity"]] += 1

    return {
        "mode": "rules",
        "summary": {
            "critical": grouped["critical"],
            "warning": grouped["warning"],
            "info": grouped["info"],
            "total": len(issues),
        },
        "issues": issues,
    }


def _issue(severity, model, field, message):
    return {
        "severity": severity,
        "model": model,
        "field": field,
        "message": message,
    }
