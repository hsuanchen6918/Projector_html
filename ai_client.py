import json
import os
import re
import urllib.error
import urllib.request


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


def openai_enabled():
    mode = os.getenv("AI_MODE", "rules").lower()
    return mode in {"openai", "external"} and bool(os.getenv("OPENAI_API_KEY"))


def call_openai_json(instructions, payload, timeout=45):
    if not openai_enabled():
        return None

    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    body = {
        "model": model,
        "instructions": instructions,
        "input": json.dumps(payload, ensure_ascii=False),
        "max_output_tokens": 1600,
    }
    req = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None

    output_text = _extract_output_text(data)
    if not output_text:
        return None
    return _parse_json_object(output_text)


def _extract_output_text(data):
    if isinstance(data, dict) and data.get("output_text"):
        return data["output_text"]

    chunks = []
    for item in data.get("output", []) if isinstance(data, dict) else []:
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                chunks.append(content["text"])
    return "\n".join(chunks).strip()


def _parse_json_object(value):
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", value)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def enhance_recommendations(rule_result):
    payload = {
        "task": "rewrite_projector_recommendations",
        "ruleResult": _compact_recommendations(rule_result),
        "outputShape": {
            "recommendations": [
                {
                    "score": "number",
                    "reasons": ["繁體中文推薦理由，最多 5 點"],
                    "cautions": ["繁體中文注意事項，最多 3 點"],
                }
            ],
            "message": "繁體中文簡短說明",
        },
    }
    instructions = (
        "你是投影機競品分析助理。只能根據輸入資料分析，不可編造規格。"
        "請保留 recommendations 的數量與排序，只改寫 reasons、cautions、message。"
        "輸出必須是 JSON object，不要 Markdown。"
    )
    ai = call_openai_json(instructions, payload)
    if not ai or "recommendations" not in ai:
        return rule_result

    merged = dict(rule_result)
    recommendations = []
    enhanced_rows = ai.get("recommendations", [])
    for index, original in enumerate(rule_result.get("recommendations", [])):
        enhanced = enhanced_rows[index] if index < len(enhanced_rows) else {}
        item = dict(original)
        item["reasons"] = enhanced.get("reasons") or original.get("reasons", [])
        item["cautions"] = enhanced.get("cautions") or original.get("cautions", [])
        recommendations.append(item)
    merged["recommendations"] = recommendations
    merged["message"] = ai.get("message") or "使用外部 AI 依本地規則候選結果產生說明。"
    merged["mode"] = "openai"
    return merged


def _compact_recommendations(rule_result):
    rows = []
    for rec in rule_result.get("recommendations", []):
        rows.append({
            "score": rec.get("score"),
            "reasons": rec.get("reasons", []),
            "cautions": rec.get("cautions", []),
            "projector": _compact_projector(rec.get("projector", {})),
        })
    return {**rule_result, "recommendations": rows}


def _compact_projector(projector):
    fields = [
        "Brand", "Model", "St. Price", "Released", "Brightness", "Resolution", "Contrast",
        "Lamp Type", "Throw Ratio", "Weight (kg)", "Noise(dB(A))", "Dolby Vision", "HDR10+",
        "MEMC", "Autofocus", "AIscreen", "Autokeystone", "Autofit", "Automove",
        "Eyesprotect", "System", "Features", "IsSWQE", "PPTX",
        "UnboxingSummary", "UnboxingPros", "UnboxingCons", "UnboxingNotes",
    ]
    return {field: projector.get(field) for field in fields if field in projector}
