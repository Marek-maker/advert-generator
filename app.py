"""
Advert Generator — Flask app for PythonAnywhere
"""
import os, sys, json, uuid, base64, re, urllib.request, urllib.error, time
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(BASE_DIR, "data", "biznis_index.json")
SHEET_ID = "1P5xuT4QJBpKaEVi0vDNgAdO1UQQzh6C39k0L8FhrFhQ"

STOCK_INDEX_CACHE = None


def load_stock_index():
    global STOCK_INDEX_CACHE
    if STOCK_INDEX_CACHE is not None:
        return STOCK_INDEX_CACHE
    if not os.path.exists(INDEX_PATH):
        return {}
    with open(INDEX_PATH, encoding="utf-8") as f:
        STOCK_INDEX_CACHE = json.load(f)
    return STOCK_INDEX_CACHE


def invalidate_stock_cache():
    global STOCK_INDEX_CACHE
    STOCK_INDEX_CACHE = None


def extract_models(text):
    if not text:
        return set()
    BRANDS = {"gigabyte", "foxconn", "asus", "intel", "amd", "nvidia", "kingston",
              "samsung", "dell", "hp", "lenovo", "a4tech", "logitech", "sony",
              "western", "seagate", "toshiba", "fujitsu", "hitachi", "liteon",
              "zalman", "benq", "philips", "sencor", "patriot", "lg", "nec",
              "brocade", "cisco", "finisar", "netgear", "nortel", "avaya",
              "infineon", "corus", "picolight", "jdsu", "adva", "agilent",
              "problabs", "d-link", "ocz", "corsair"}
    models = set()
    for m in re.findall(r'\b[A-Za-z0-9][A-Za-z0-9\-\./]+[A-Za-z0-9]\b', text):
        low = m.lower()
        if len(m) >= 4 and low not in BRANDS and not low.isalpha():
            models.add(low)
    return models


def match_stock_items(analysis_text, category, params_text, top_n=3):
    from difflib import SequenceMatcher
    index = load_stock_index()
    if not index:
        return []
    query_text = f"{analysis_text or ''} {params_text or ''}"
    query_models = extract_models(query_text)
    query_lower = query_text.lower()
    scores = []
    for poradie, item in index.items():
        name = item.get("nazov", "").lower()
        cat = item.get("kategoria", "").lower()
        item_text = f"{name} {cat}"
        item_models = extract_models(item.get("nazov", ""))
        shared = query_models & item_models
        if shared:
            base = 0.85
            bonus = min(len(shared) * 0.1, 0.15)
            scores.append((poradie, base + bonus, item, "model"))
            continue
        ratio = SequenceMatcher(None, query_lower[:50], name[:50]).ratio()
        if ratio > 0.4:
            scores.append((poradie, ratio, item, "name"))
        query_tokens = set(re.findall(r'\b[a-z0-9]+\b', query_lower))
        item_tokens = set(re.findall(r'\b[a-z0-9]+\b', name))
        stopwords = {"the", "and", "for", "with", "from", "sas", "gb", "tb", "hz", "cmos"}
        query_tokens = {t for t in query_tokens if len(t) >= 3 and t not in stopwords}
        item_tokens = {t for t in item_tokens if len(t) >= 3 and t not in stopwords}
        if query_tokens and item_tokens:
            overlap = len(query_tokens & item_tokens)
            total = len(query_tokens | item_tokens)
            if total > 0:
                jaccard = overlap / total
                if jaccard > 0.25 and ratio > 0.2:
                    combined = max(ratio, jaccard) * 0.8 + min(ratio, jaccard) * 0.2
                    if combined > 0.3:
                        scores.append((poradie, combined, item, "token"))
    best_per_item = {}
    for poradie, score, item, method in scores:
        if poradie not in best_per_item or score > best_per_item[poradie][0]:
            best_per_item[poradie] = (score, item, method)
    ranked = sorted(best_per_item.items(), key=lambda x: -x[1][0])
    results = []
    for poradie, (score, item, method) in ranked:
        if score >= 0.35:
            results.append({
                "poradie": poradie, "score": round(score, 2), "method": method,
                "nazov": item.get("nazov", ""), "kategoria": item.get("kategoria", ""),
                "predajna_cena": item.get("predajna_cena", ""),
                "pocet": item.get("pocet", "1"),
                "photos_count": len(item.get("photos", [])),
                "stav": item.get("stav", "sklad"),
            })
        if len(results) >= top_n:
            break
    return results


TEMPLATES = {
    "RAM": {
        "emoji": "🧠",
        "fields": [
            {"key": "type", "label": "Type", "type": "select", "options": ["DDR3", "DDR4", "DDR5", "DDR2", "Unknown"]},
            {"key": "capacity", "label": "Capacity", "type": "select", "options": ["1GB", "2GB", "4GB", "8GB", "16GB", "32GB", "64GB"]},
            {"key": "speed", "label": "Speed", "type": "select", "options": ["800", "1066", "1333", "1600", "1866", "2133", "2400", "2666", "3000", "3200", "3600", "4800", "5200", "5600", "6000", "6400", "7200", "8000"]},
            {"key": "form_factor", "label": "Form Factor", "type": "select", "options": ["SODIMM (laptop)", "DIMM (desktop)"], "default": "SODIMM (laptop)"},
            {"key": "brand", "label": "Brand", "type": "text"},
            {"key": "part_number", "label": "Part Number", "type": "text"},
            {"key": "condition", "label": "Condition", "type": "select", "options": ["New", "Like New", "Used - Good", "Used - Fair", "Tested", "For Parts"]},
            {"key": "quantity", "label": "Quantity", "type": "number", "default": 1},
            {"key": "price", "label": "Price (€)", "type": "number"},
        ],
        "description_template": "{brand} {capacity} {type} {speed}MHz {form_factor} RAM\n\nPart: {part_number}\nCondition: {condition}\nQuantity: {quantity}\n\n📦 Ready to ship\n✅ Tested and working\n\nPrice: {price}€",
    },
    "Notebook": {
        "emoji": "💻",
        "fields": [
            {"key": "brand", "label": "Brand", "type": "text"},
            {"key": "model", "label": "Model", "type": "text"},
            {"key": "processor", "label": "Processor", "type": "text"},
            {"key": "ram", "label": "RAM", "type": "text"},
            {"key": "storage", "label": "Storage", "type": "text"},
            {"key": "screen_size", "label": "Screen Size", "type": "select", "options": ["10\"", "11.6\"", "13.3\"", "14\"", "15.6\"", "16\"", "17.3\"", "18\"", "Unknown"]},
            {"key": "resolution", "label": "Resolution", "type": "select", "options": ["1366x768", "1920x1080", "2560x1440", "2880x1800", "3200x2000", "3840x2160", "Unknown"]},
            {"key": "gpu", "label": "GPU", "type": "text"},
            {"key": "condition", "label": "Condition", "type": "select", "options": ["New", "Like New", "Used - Excellent", "Used - Good", "Used - Fair", "For Parts"]},
            {"key": "color", "label": "Color", "type": "text"},
            {"key": "year", "label": "Year", "type": "text"},
            {"key": "price", "label": "Price (€)", "type": "number"},
        ],
        "description_template": "{brand} {model} Notebook\n\nSpecs:\n• CPU: {processor}\n• RAM: {ram}\n• Storage: {storage}\n• Display: {screen_size} {resolution}\n• GPU: {gpu}\n• Color: {color}\n• Year: {year}\n\nCondition: {condition}\n\n💻 Fully functional\n🔋 Battery tested\n\nPrice: {price}€",
    },
    "Monitor": {
        "emoji": "🖥️",
        "fields": [
            {"key": "brand", "label": "Brand", "type": "text"},
            {"key": "model", "label": "Model", "type": "text"},
            {"key": "size", "label": "Size", "type": "select", "options": ["19\"", "21.5\"", "22\"", "24\"", "25\"", "27\"", "28\"", "32\"", "34\"", "38\"", "42\"", "49\"", "Unknown"]},
            {"key": "resolution", "label": "Resolution", "type": "select", "options": ["1366x768", "1600x900", "1920x1080", "2560x1080", "2560x1440", "3440x1440", "3840x2160", "Unknown"]},
            {"key": "panel_type", "label": "Panel Type", "type": "select", "options": ["IPS", "TN", "VA", "OLED", "PLS", "Unknown"]},
            {"key": "refresh_rate", "label": "Refresh Rate", "type": "select", "options": ["60Hz", "75Hz", "100Hz", "120Hz", "144Hz", "165Hz", "240Hz", "360Hz", "Unknown"]},
            {"key": "condition", "label": "Condition", "type": "select", "options": ["New", "Like New", "Used - Excellent", "Used - Good", "Used - Fair"]},
            {"key": "connectivity", "label": "Connectivity", "type": "text"},
            {"key": "price", "label": "Price (€)", "type": "number"},
        ],
        "description_template": "{brand} {model} {size} {panel_type} Monitor\n\nSpecs:\n• Resolution: {resolution}\n• Refresh Rate: {refresh_rate}\n• Panel: {panel_type}\n• Connectivity: {connectivity}\n\nCondition: {condition}\n\n🖥️ No dead pixels\n✅ Tested with all inputs\n\nPrice: {price}€",
    },
    "Other": {
        "emoji": "📦",
        "fields": [
            {"key": "title", "label": "Title", "type": "text"},
            {"key": "category", "label": "Category", "type": "text"},
            {"key": "brand", "label": "Brand", "type": "text"},
            {"key": "model", "label": "Model", "type": "text"},
            {"key": "condition", "label": "Condition", "type": "select", "options": ["New", "Like New", "Used - Excellent", "Used - Good", "Used - Fair", "For Parts"]},
            {"key": "description", "label": "Description", "type": "textarea"},
            {"key": "price", "label": "Price (€)", "type": "number"},
        ],
        "description_template": "{title}\n\nBrand: {brand} | Model: {model}\nCondition: {condition}\n\n{description}\n\nPrice: {price}€",
    }
}


GOOGLE_API_KEY = None
def get_gemini_key():
    global GOOGLE_API_KEY
    if GOOGLE_API_KEY:
        return GOOGLE_API_KEY
    for p in [
        os.path.join(BASE_DIR, ".env"),
        os.path.join(os.path.expanduser("~"), ".env"),
    ]:
        if os.path.exists(p):
            with open(p) as f:
                for line in f:
                    if line.startswith("GOOGLE_API_KEY=") and not line.startswith("#"):
                        GOOGLE_API_KEY = line.strip().split("=", 1)[1]
                        return GOOGLE_API_KEY
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    return GOOGLE_API_KEY


def analyze_image(image_b64):
    api_key = get_gemini_key()
    if not api_key:
        return {"error": "No Gemini API key"}, 0
    t0 = time.time()
    prompt = 'Identify this tech item. Return JSON: {"category":"RAM|Notebook|Monitor|Other","description":"brief 1-line","parameters":{all detectable specs}}. Fill only what you see, empty strings for unknown.'
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite-001:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [
            {"text": prompt},
            {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}}
        ]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024}
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read())
        text = result["candidates"][0]["content"]["parts"][0]["text"]
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            parsed["timing"] = {"gemini_ms": int((time.time() - t0) * 1000)}
            return parsed, int((time.time() - t0) * 1000)
        return {"error": "No JSON", "raw": text[:200]}, int((time.time() - t0) * 1000)
    except urllib.error.HTTPError as e:
        return {"error": f"API HTTP {e.code}"}, int((time.time() - t0) * 1000)
    except Exception as e:
        return {"error": str(e)}, int((time.time() - t0) * 1000)


def generate_advert(params, template):
    api_key = get_gemini_key()
    filled = template["description_template"].format(**{k: v or "" for k, v in params.items()})
    if not api_key:
        return {"description": filled, "source": "template"}
    prompt = f"""Generate a clean, professional advert description for selling tech hardware.
Category: {params.get('_category', 'Unknown')}
Parameters: {json.dumps({k:v for k,v in params.items() if not k.startswith('_')}, indent=2)}
Write a product description with:
1. Title line
2. Key specs as bullet points
3. Condition notes
4. Price
Keep it concise, factual, and ready to post on a marketplace."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite-001:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1024}
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read())
        text = result["candidates"][0]["content"]["parts"][0]["text"]
        return {"description": text, "source": "gemini"}
    except:
        return {"description": filled, "source": "template"}


# ── Routes ───────────────────────────────────────────────────────

@app.route("/")
@app.route("/health")
def health():
    return jsonify({"ok": True, "status": "alive", "service": "advert-generator"})


@app.route("/categories", methods=["POST"])
def categories():
    cats = {k: {"emoji": v["emoji"], "fields": v["fields"]} for k, v in TEMPLATES.items()}
    return jsonify({"ok": True, "categories": cats})


@app.route("/upload", methods=["POST"])
def upload():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": False, "error": "Bad JSON"}), 400
    photos_b64 = data.get("photos", [])
    if not photos_b64:
        return jsonify({"ok": False, "error": "No photos"}), 400

    photo_b64 = photos_b64[0]
    raw_b64 = photo_b64.split(",", 1)[1] if "," in photo_b64 else photo_b64

    t0 = time.time()
    analysis, gemini_ms = analyze_image(raw_b64)
    total_ms = int((time.time() - t0) * 1000)

    if "error" in analysis:
        return jsonify({"ok": False, "error": analysis["error"], "timing": {"gemini_ms": gemini_ms, "total_ms": total_ms}})

    category = analysis.get("category", "Other")
    if category not in TEMPLATES:
        category = "Other"
    template = TEMPLATES[category]
    params = analysis.get("parameters", {})
    filled = {}
    for field in template["fields"]:
        k = field["key"]
        val = params.get(k, params.get(field["label"].lower(), ""))
        if not val:
            val = field.get("default", "")
        filled[k] = val

    params_text = " ".join(f"{k}:{v}" for k, v in params.items() if v)
    matches = match_stock_items(
        analysis_text=analysis.get("description", ""),
        category=category, params_text=params_text, top_n=3
    )
    match_status = "matched" if matches else "none"

    return jsonify({
        "ok": True, "status": "complete", "category": category,
        "emoji": template["emoji"], "fields": template["fields"],
        "filled": filled, "description": analysis.get("description", ""),
        "matches": matches, "match_status": match_status,
        "timing": {"gemini_ms": gemini_ms, "total_ms": total_ms},
    })


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": False, "error": "Bad JSON"}), 400
    category = data.get("category", "Other")
    params = data.get("params", {})
    params["_category"] = category
    if category in TEMPLATES:
        advert = generate_advert(params, TEMPLATES[category])
    else:
        advert = {"description": "No template", "source": "none"}
    return jsonify({"ok": True, "description": advert["description"], "source": advert["source"]})


@app.route("/pair", methods=["POST"])
def pair():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": False, "error": "Bad JSON"}), 400
    poradie = str(data.get("poradie", ""))
    action = data.get("action", "pair")
    description = data.get("description", "")

    if not poradie:
        return jsonify({"ok": False, "error": "Missing poradie"}), 400

    index = load_stock_index()
    if poradie not in index:
        return jsonify({"ok": False, "error": f"Item #{poradie} not found"}), 404

    item = index[poradie]

    if action == "pair":
        photo = data.get("photo", {})
        if photo and photo.get("filename"):
            photo_ref = {"file": photo["filename"], "path": "(uploaded)", "id": photo.get("id", "")}
            if "photos" not in item:
                item["photos"] = []
            if photo_ref not in item["photos"]:
                item["photos"].append(photo_ref)
        item["stav"] = "nafotené"
        item["last_check"] = str(datetime.now().date())
        if description and description not in item.get("nazov", ""):
            item["poznamky"] = (item.get("poznamky", "") + f"; {description}").strip("; ")
        msg = f"Photo paired with #{poradie} ({item['nazov']})"

    elif action == "increase":
        current_qty = int(item.get("pocet", "1") or "1")
        item["pocet"] = str(current_qty + 1)
        item["last_check"] = str(datetime.now().date())
        msg = f"Count increased for #{poradie}: {current_qty} → {current_qty + 1}"
    else:
        return jsonify({"ok": False, "error": f"Unknown action: {action}"}), 400

    invalidate_stock_cache()
    return jsonify({
        "ok": True, "message": msg, "poradie": poradie,
        "item": {
            "nazov": item.get("nazov", ""), "pocet": item.get("pocet", "1"),
            "photos_count": len(item.get("photos", [])), "stav": item.get("stav", "sklad"),
        }
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 Advert Generator Flask on :{port}")
    print(f"🔑 Gemini key: {'found' if get_gemini_key() else 'MISSING'}")
    stock_count = len(load_stock_index())
    print(f"📦 Stock index: {stock_count} items")
    app.run(host="0.0.0.0", port=port, debug=False)
