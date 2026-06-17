import argparse
import calendar
import datetime as dt
import difflib
import email.utils
import hashlib
import html
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import ai_client


WORKING_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCES_PATH = os.path.join(WORKING_DIR, "news_sources.json")
NEWS_PATH = os.path.join(WORKING_DIR, "news_data.json")
LOCK_PATH = os.path.join(WORKING_DIR, ".news_collector.lock")
GOOGLE_NEWS_URL = "https://news.google.com/rss/search"
USER_AGENT = "Mozilla/5.0 (compatible; SWQE-Projector-News/1.0)"

PROJECTOR_TERMS = [
    "projector", "projection technology", "投影機", "投影仪", "投影技術", "投影技术",
    "プロジェクター", "投写技術", "laser tv", "雷射電視", "激光电视",
    "laser projector", "雷射投影", "激光投影", "レーザープロジェクター",
]

DISPLAY_TECH_TERMS = ["3lcd", "lcos", "sxrd", "d-ila", "dmd", "digital micromirror"]
OPTICAL_ENGINE_TERMS = ["optical engine", "light engine", "光機", "光机", "光学エンジン"]
DISPLAY_CONTEXT_TERMS = [
    "projector", "projection", "display", "cinema", "投影", "顯示", "显示",
    "プロジェクター", "投写", "ディスプレイ", "ar", "vr", "xr", "眼鏡", "眼镜",
]
EXCLUSION_TERMS = [
    "data loss prevention", "google workspace policy", "workspace向けai搭載dlp",
    "cybersecurity", "資安", "資料外洩防護", "数据防泄漏", "情報漏洩",
    "x光機", "x光机", "光機學院", "光机学院",
]

TOPIC_TERMS = {
    "新品發表": ["launch", "announce", "unveil", "release", "new projector", "發表", "发布", "新品", "発売"],
    "DLP／DMD": ["dlp", "dmd", "digital micromirror"],
    "3LCD": ["3lcd", "lcd projector", "液晶投影"],
    "LCoS": ["lcos", "sxrd", "d-ila"],
    "雷射光源": ["laser", "雷射", "激光", "レーザー"],
    "LED 光源": ["led projector", "led light source", "led 投影", "led光源"],
    "光機／光學引擎": ["optical engine", "light engine", "光機", "光机", "光学エンジン"],
    "影像晶片／處理": ["soc", "chipset", "processor", "memc", "晶片", "芯片", "画像処理"],
    "供應鏈／市場": ["market", "shipment", "revenue", "supply chain", "市場", "出貨", "供应链", "売上"],
    "專利／研發": ["patent", "research", "development", "專利", "研发", "特許", "研究開発"],
}

BRAND_TERMS = {
    "Acer": ["acer", "宏碁"],
    "Anker Nebula": ["anker", "nebula"],
    "BenQ": ["benq", "明基"],
    "Aladdin X": ["aladdin x"],
    "Christie": ["christie", "科視", "科视"],
    "Dangbei": ["dangbei", "當貝", "当贝"],
    "Epson": ["epson", "愛普生", "エプソン"],
    "Hisense": ["hisense", "海信"],
    "JMGO": ["jmgo", "堅果", "坚果"],
    "Leica": ["leica", "徠卡", "徕卡", "ライカ"],
    "LG": ["lg cinebeam", "lg projector"],
    "Optoma": ["optoma", "奧圖碼", "奥图码"],
    "Panasonic": ["panasonic projector", "松下投影"],
    "Samsung": ["samsung projector", "the premiere", "freestyle"],
    "Sharp": ["sharp projector"],
    "Sony": ["sony projector", "sony projection", "sxrd"],
    "Texas Instruments": ["texas instruments", "ti dlp"],
    "ViewSonic": ["viewsonic", "優派", "优派"],
    "XGIMI": ["xgimi", "極米", "极米"],
}

OFFICIAL_DOMAINS = {
    "acer.com", "anker.com", "benq.com", "dangbei.com", "epson.com", "hisense.com",
    "jmgo.com", "lg.com", "optoma.com", "samsung.com", "sharp.com", "sony.com",
    "ti.com", "viewsonic.com", "xgimi.com",
}

ZH_CN_TO_TW = str.maketrans({
    "仪": "儀", "术": "術", "机": "機", "显": "顯", "屏": "螢", "激": "雷",
    "发": "發", "布": "布", "开": "開", "卖": "賣", "价": "價", "级": "級",
    "质": "質", "产": "產", "业": "業", "动": "動", "态": "態", "应": "應",
    "链": "鏈", "场": "場", "数": "數", "据": "據", "处": "處", "带": "帶",
    "灯": "燈", "车": "車", "载": "載", "华": "華", "为": "為", "与": "與",
    "网": "網", "东": "東", "龙": "龍", "飞": "飛", "达": "達", "过": "過",
    "镜": "鏡", "众": "眾", "广": "廣", "实": "實", "验": "驗", "万": "萬",
    "长": "長", "后": "後", "体": "體", "头": "頭", "声": "聲", "双": "雙",
    "对": "對", "会": "會", "电": "電", "湾": "灣", "这": "這", "该": "該",
    "优": "優", "选": "選", "预": "預", "测": "測", "轻": "輕", "续": "續",
    "国": "國", "热": "熱", "制": "製",
})

ZH_CN_PHRASES = {
    "投影仪": "投影機",
    "激光": "雷射",
    "三色激光": "三色雷射",
    "光机": "光機",
    "芯片": "晶片",
    "发布": "發布",
    "开卖": "開賣",
    "热卖": "熱賣",
    "中国制造": "中國製造",
    "上市": "上市",
    "大屏": "大螢幕",
    "综合续航": "綜合續航",
    "供应链": "供應鏈",
    "智能": "智慧",
}

JA_PHRASES = [
    ("予約販売を開始", "開始預購"),
    ("販売を開始", "開始銷售"),
    ("提供開始", "開始提供"),
    ("発表会レポート", "發表會報導"),
    ("発売", "開賣"),
    ("発表", "發表"),
    ("新モデル", "新機型"),
    ("対応モデル", "支援機型"),
    ("4K対応", "支援 4K"),
    ("3色レーザー", "三色雷射"),
    ("3色", "三色"),
    ("レーザー搭載", "搭載雷射"),
    ("レーザープロジェクター", "雷射投影機"),
    ("スマートプロジェクター", "智慧投影機"),
    ("ミニプロジェクター", "迷你投影機"),
    ("プロジェクター用", "投影機用"),
    ("プロジェクター", "投影機"),
    ("投写技術", "投影技術"),
    ("照明一体型", "照明一體型"),
    ("短焦点", "短焦"),
    ("大画面", "大畫面"),
    ("複数台", "多台"),
    ("活用する際", "使用時"),
    ("映像調整", "影像調整"),
    ("運用ワークフロー", "操作流程"),
    ("改善し", "改善"),
    ("実現", "實現"),
    ("新機能", "新功能"),
    ("企業・法人向け", "企業法人用"),
    ("製品・サービス", "產品與服務"),
    ("映画鑑賞", "電影觀賞"),
    ("アニメ鑑賞", "動畫觀賞"),
    ("映画", "電影"),
    ("アニメ", "動畫"),
    ("癒やし", "療癒"),
    ("見るのが好きです", "喜歡觀看"),
    ("圧倒的映像美", "壓倒性的影像美"),
    ("臨場感", "臨場感"),
    ("機能性", "功能性"),
    ("最上位モデル", "最高階機型"),
    ("暮らしに寄り添って", "貼近日常生活"),
    ("毎日", "每天"),
    ("楽しく", "更有趣"),
    ("快適", "舒適"),
    ("再挑戦", "再挑戰"),
    ("手のひらサイズ", "掌上尺寸"),
    ("軽量", "輕量"),
    ("日常を彩る", "為日常增添色彩"),
    ("囲み", "圍繞"),
    ("説明", "說明"),
    ("耳を傾ける", "聆聽"),
    ("参加者", "參加者"),
    ("新型", "新款"),
    ("実力", "實力"),
    ("体験", "體驗"),
    ("自宅", "家中"),
    ("映画館", "電影院"),
    ("天井", "天花板"),
    ("置いてみない", "試著放置"),
    ("楽しむ", "享受"),
    ("ある暮らし", "的生活"),
    ("日本上陸", "登陸日本"),
    ("鮮明", "清晰"),
    ("明るく", "更明亮"),
    ("必需品", "必需品"),
    ("既存ユーザー", "既有用戶"),
    ("特別", "特別"),
    ("重さ", "重量"),
    ("筐体", "機身"),
    ("中に", "中"),
    ("解像度", "解析度"),
    ("搭載", "搭載"),
    ("モデル", "機型"),
    ("市場予測", "市場預測"),
    ("世界市場予測", "全球市場預測"),
    ("おすすめ", "推薦"),
    ("人気ランキング", "人氣排名"),
    ("導入理由", "導入原因"),
    ("施設", "場館"),
    ("最大", "最大"),
    ("最新", "最新"),
    ("半額", "半價"),
    ("割引", "折扣"),
    ("ニュース", "新聞"),
    ("レビュー", "評測"),
    ("スクリーン", "螢幕"),
    ("ホームシアター", "家庭劇院"),
    ("シアター", "劇院"),
    ("オーディオ", "音響"),
    ("スマートフォン", "智慧型手機"),
    ("接続", "連接"),
    ("選び方", "選購方式"),
    ("用途別", "依用途"),
    ("光源別", "依光源"),
    ("解像度別", "依解析度"),
    ("輝度", "亮度"),
    ("画面", "畫面"),
    ("市場", "市場"),
]


def utc_now():
    return dt.datetime.now(dt.timezone.utc)


def clean_text(value):
    text = html.unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def strip_source_suffix(title):
    return re.sub(r"\s+-\s+[^-]{2,80}$", "", title or "").strip()


def translate_cn_title(title):
    translated = strip_source_suffix(title)
    for source, target in ZH_CN_PHRASES.items():
        translated = translated.replace(source, target)
    return translated.translate(ZH_CN_TO_TW)


def translate_ja_title(title):
    translated = strip_source_suffix(title)
    for source, target in JA_PHRASES:
        translated = translated.replace(source, target)
    translated = translated.replace("「", "「").replace("」", "」")
    translated = re.sub(r"【([^】]+)】", r"【\1】", translated)
    return translated


def localized_title(title, language):
    if language == "zh-CN":
        return translate_cn_title(title)
    if language == "ja":
        return translate_ja_title(title)
    if language == "zh-TW":
        return strip_source_suffix(title)
    return strip_source_suffix(title)


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as source_file:
            return json.load(source_file)
    except (OSError, json.JSONDecodeError):
        return default


def atomic_write_json(path, value):
    directory = os.path.dirname(path)
    fd, temp_path = tempfile.mkstemp(prefix=".news_", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(value, output, ensure_ascii=False, indent=2)
            output.write("\n")
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def acquire_lock():
    try:
        descriptor = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        os.close(descriptor)
        return True
    except FileExistsError:
        try:
            age = utc_now().timestamp() - os.path.getmtime(LOCK_PATH)
            if age > 3600:
                os.remove(LOCK_PATH)
                return acquire_lock()
        except OSError:
            pass
        return False


def release_lock():
    try:
        os.remove(LOCK_PATH)
    except OSError:
        pass


def google_news_feed_url(source, start_date=None, end_date=None):
    language = source.get("language", "en-US")
    country_code = {
        "zh-TW": ("TW", "zh-Hant"),
        "zh-CN": ("CN", "zh-Hans"),
        "ja": ("JP", "ja"),
        "en-US": ("US", "en"),
    }.get(language, ("US", "en"))
    query = source["query"]
    if start_date:
        query = f"{query} after:{start_date.isoformat()}"
    if end_date:
        query = f"{query} before:{end_date.isoformat()}"

    params = {
        "q": query,
        "hl": language,
        "gl": country_code[0],
        "ceid": f"{country_code[0]}:{country_code[1]}",
    }
    return f"{GOOGLE_NEWS_URL}?{urllib.parse.urlencode(params)}"


def fetch_bytes(url, timeout=25):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def parse_date(value):
    if not value:
        return None
    parsed = email.utils.parsedate(value)
    if parsed:
        timestamp = calendar.timegm(parsed)
        return dt.datetime.fromtimestamp(timestamp, dt.timezone.utc)
    try:
        parsed_iso = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed_iso if parsed_iso.tzinfo else parsed_iso.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def child_text(element, names):
    for child in list(element):
        tag = child.tag.rsplit("}", 1)[-1]
        if tag in names and child.text:
            return child.text
    return ""


def parse_feed(xml_data, source):
    root = ET.fromstring(xml_data)
    items = []
    for entry in root.iter():
        tag = entry.tag.rsplit("}", 1)[-1]
        if tag not in {"item", "entry"}:
            continue

        title = clean_text(child_text(entry, {"title"}))
        link = clean_text(child_text(entry, {"link"}))
        if not link:
            for child in list(entry):
                if child.tag.rsplit("}", 1)[-1] == "link" and child.attrib.get("href"):
                    link = child.attrib["href"]
                    break

        description = clean_text(child_text(entry, {"description", "summary", "content"}))
        published = child_text(entry, {"pubDate", "published", "updated"})
        publisher = ""
        publisher_url = ""
        for child in list(entry):
            if child.tag.rsplit("}", 1)[-1] == "source":
                publisher = clean_text(child.text)
                publisher_url = child.attrib.get("url", "")
                break

        if title and link:
            items.append({
                "title": title,
                "description": description,
                "source_url": link,
                "publisher_url": publisher_url,
                "source": publisher or source["name"],
                "published": parse_date(published),
                "country": source["country"],
                "language": source["language"],
            })
    return items


def normalized_title(value):
    value = value.lower()
    value = re.sub(r"\s+-\s+[^-]{2,80}$", "", value)
    value = re.sub(r"[\W_]+", "", value, flags=re.UNICODE)
    return value


def is_relevant(item):
    haystack = f"{item['title']} {item['description']}".lower()
    if any(term in haystack for term in EXCLUSION_TERMS):
        return False
    if any(term in haystack for term in PROJECTOR_TERMS):
        return True
    if any(term in haystack for term in DISPLAY_TECH_TERMS):
        return True
    has_display_context = any(term in haystack for term in DISPLAY_CONTEXT_TERMS)
    if "dlp" in haystack and has_display_context:
        return True
    return any(term in haystack for term in OPTICAL_ENGINE_TERMS) and has_display_context


def classify(item):
    haystack = f"{item['title']} {item['description']}".lower()
    topics = [
        topic for topic, terms in TOPIC_TERMS.items()
        if any(term in haystack for term in terms)
    ]
    brands = [
        brand for brand, terms in BRAND_TERMS.items()
        if any(term in haystack for term in terms)
    ]
    return topics[:4] or ["產業動態"], brands


def domain_is_official(url):
    hostname = (urllib.parse.urlparse(url).hostname or "").lower()
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in OFFICIAL_DOMAINS)


def basic_summary(item, topics, brands):
    focus = "、".join((brands + topics)[:4]) or "投影顯示產業"
    return (
        f"此則消息的可辨識重點為 {focus}，原始標題為「{item['title']}」。"
        "目前 RSS 資訊有限，詳細產品規格、技術數據與發布範圍仍應以原文為準。"
    )


def make_news_item(item):
    topics, brands = classify(item)
    published = item["published"] or utc_now()
    publisher_url = item.get("publisher_url") or ""
    stable_value = item["source_url"] or normalized_title(item["title"])
    return {
        "id": hashlib.sha256(stable_value.encode("utf-8")).hexdigest()[:16],
        "title": item["title"],
        "title_zh_tw": localized_title(item["title"], item["language"]),
        "summary_zh_tw": basic_summary(item, topics, brands),
        "source": item["source"],
        "source_url": item["source_url"],
        "published_at": published.date().isoformat(),
        "country": item["country"],
        "language": item["language"],
        "brands": brands,
        "topics": topics,
        "is_official": domain_is_official(publisher_url),
        "summary_mode": "rules",
        "collected_at": utc_now().isoformat(timespec="seconds"),
    }


def enhance_with_ai(items):
    if not items or not ai_client.openai_enabled():
        return items

    for start in range(0, len(items), 8):
        batch = items[start:start + 8]
        enhanced = ai_client.summarize_news_items(batch)
        if not enhanced:
            continue
        by_id = {row.get("id"): row for row in enhanced if row.get("id")}
        for item in batch:
            result = by_id.get(item["id"])
            if not result:
                continue
            item["title"] = clean_text(result.get("title_zh_tw")) or item["title"]
            item["title_zh_tw"] = item["title"]
            item["summary_zh_tw"] = clean_text(result.get("summary_zh_tw")) or item["summary_zh_tw"]
            item["summary_mode"] = "openai"
            if isinstance(result.get("topics"), list) and result["topics"]:
                item["topics"] = [clean_text(topic) for topic in result["topics"][:4] if clean_text(topic)]
    return items


def merge_news(existing, incoming, retention_days, max_items):
    cutoff = utc_now().date() - dt.timedelta(days=retention_days)
    merged = {}
    for item in existing + incoming:
        relevance_item = {
            "title": item.get("title", ""),
            "description": item.get("summary_zh_tw", ""),
        }
        if not is_relevant(relevance_item):
            continue
        try:
            published = dt.date.fromisoformat(item.get("published_at", ""))
        except ValueError:
            published = utc_now().date()
        if published < cutoff:
            continue
        key = item.get("source_url") or normalized_title(item.get("title", ""))
        if key:
            merged[key] = item
    sorted_items = sorted(
        merged.values(),
        key=lambda item: (item.get("published_at", ""), item.get("collected_at", "")),
        reverse=True,
    )

    deduplicated = []
    for item in sorted_items:
        if any(same_news_event(item, kept) for kept in deduplicated):
            continue
        deduplicated.append(item)
        if len(deduplicated) >= max_items:
            break
    return deduplicated


def model_tokens(title):
    tokens = set(re.findall(r"\b[a-z]*\d+[a-z0-9-]*\b", title.lower()))
    return tokens - {"3d", "4k", "8k", "2025", "2026", "2027"}


def same_news_event(left, right):
    left_title = normalized_title(left.get("title", ""))
    right_title = normalized_title(right.get("title", ""))
    if not left_title or not right_title:
        return False
    if left_title in right_title or right_title in left_title:
        shorter = min(len(left_title), len(right_title))
        if shorter >= 18:
            return True
    similarity = difflib.SequenceMatcher(None, left_title, right_title).ratio()
    if similarity >= 0.78:
        return True
    shared_brands = set(left.get("brands", [])) & set(right.get("brands", []))
    shared_models = model_tokens(left_title) & model_tokens(right_title)
    return bool(shared_brands and shared_models and left.get("published_at") == right.get("published_at"))


def parse_iso_date(value):
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"Invalid date: {value}. Use YYYY-MM-DD.") from error


def month_windows(start_date, end_date):
    current = start_date.replace(day=1)
    while current < end_date:
        if current.month == 12:
            next_month = dt.date(current.year + 1, 1, 1)
        else:
            next_month = dt.date(current.year, current.month + 1, 1)
        yield max(start_date, current), min(end_date, next_month)
        current = next_month


def collect(days=7, max_items=100, from_date=None, to_date=None, retention_days=45):
    sources = load_json(SOURCES_PATH, [])
    if not sources:
        raise RuntimeError("news_sources.json 沒有可用來源")

    end_date = to_date or (utc_now().date() + dt.timedelta(days=1))
    start_date = from_date or (utc_now().date() - dt.timedelta(days=days))
    cutoff = dt.datetime.combine(start_date, dt.time.min, tzinfo=dt.timezone.utc)
    candidates = []
    errors = []
    seen_titles = set()

    windows = list(month_windows(start_date, end_date)) if from_date else [(start_date, end_date)]
    for source in sources:
        for window_start, window_end in windows:
            url = source.get("url") or google_news_feed_url(source, window_start, window_end)
            try:
                feed_items = parse_feed(fetch_bytes(url), source)
            except (OSError, urllib.error.URLError, ET.ParseError) as error:
                errors.append(f"{source.get('name', url)}: {error}")
                continue

            for item in feed_items:
                if item["published"]:
                    if item["published"] < cutoff:
                        continue
                    if item["published"].date() >= end_date:
                        continue
                title_key = normalized_title(item["title"])
                if not title_key or title_key in seen_titles or not is_relevant(item):
                    continue
                seen_titles.add(title_key)
                candidates.append(make_news_item(item))

    candidates.sort(key=lambda item: item["published_at"], reverse=True)
    candidates = enhance_with_ai(candidates[:max_items])
    existing = load_json(NEWS_PATH, [])
    if not isinstance(existing, list):
        existing = []
    merged = merge_news(existing, candidates, retention_days=retention_days, max_items=max_items)
    for item in merged:
        if item.get("summary_mode") == "openai":
            continue
        item["summary_zh_tw"] = basic_summary(
            {"title": item.get("title", "")},
            item.get("topics", []),
            item.get("brands", []),
        )
        item["summary_mode"] = "rules"
        item["title_zh_tw"] = localized_title(item.get("title", ""), item.get("language", ""))
    atomic_write_json(NEWS_PATH, merged)
    return {
        "sources": len(sources),
        "fetched": len(candidates),
        "stored": len(merged),
        "ai_mode": "openai" if ai_client.openai_enabled() else "rules",
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser(description="Collect and summarize projector industry news.")
    parser.add_argument("--days", type=int, default=7, help="Only collect articles from the last N days.")
    parser.add_argument("--max-items", type=int, default=100, help="Maximum items stored in news_data.json.")
    parser.add_argument("--from-date", type=parse_iso_date, help="Collect articles published on or after YYYY-MM-DD.")
    parser.add_argument("--to-date", type=parse_iso_date, help="Collect articles published before YYYY-MM-DD.")
    parser.add_argument("--retention-days", type=int, default=45, help="Keep stored articles from the last N days.")
    args = parser.parse_args()

    if not acquire_lock():
        print("News collection is already running.", file=sys.stderr)
        return 2
    try:
        result = collect(
            days=max(args.days, 1),
            max_items=max(args.max_items, 1),
            from_date=args.from_date,
            to_date=args.to_date,
            retention_days=max(args.retention_days, 1),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["fetched"] or result["stored"] else 1
    finally:
        release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
