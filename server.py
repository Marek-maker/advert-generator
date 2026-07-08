#!/usr/bin/env python3
"""
Advert Generator Server
Serves Mini App + Vision analysis + Advert generation
"""

import os, sys, json, uuid, base64, re, urllib.request, urllib.error
from http.server import HTTPServer, SimpleHTTPRequestHandler
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

PHOTOS_DB = os.path.join(UPLOAD_DIR, "_received.json")
ADVERTS_DIR = os.path.join(BASE_DIR, "adverts")
os.makedirs(ADVERTS_DIR, exist_ok=True)

HERMES_HOME = os.path.join(os.environ.get("HOME", "C:/Users/ratze"), "AppData/Local/hermes")
INDEX_PATH = os.path.join(HERMES_HOME, "biznis_index.json")

# Also check project-local data/ dir (for Render deployment)
_PROJECT_INDEX = os.path.join(BASE_DIR, "data", "biznis_index.json")
if not os.path.exists(INDEX_PATH) and os.path.exists(_PROJECT_INDEX):
    INDEX_PATH = _PROJECT_INDEX

SHEET_ID = "1P5xuT4QJBpKaEVi0vDNgAdO1UQQzh6C39k0L8FhrFhQ"

# ── Stock Matching ────────────────────────────────────────────────

STOCK_INDEX_CACHE = None

def load_stock_index():
    global STOCK_INDEX_CACHE
    if STOCK_INDEX_CACHE is not None:
        return STOCK_INDEX_CACHE
    if not os.path.exists(INDEX_PATH):
        print(f"  ⚠ No stock index at {INDEX_PATH}")
        return {}
    with open(INDEX_PATH, encoding="utf-8") as f:
        STOCK_INDEX_CACHE = json.load(f)
    print(f"  📦 Stock index loaded: {len(STOCK_INDEX_CACHE)} items")
    return STOCK_INDEX_CACHE

def invalidate_stock_cache():
    global STOCK_INDEX_CACHE
    STOCK_INDEX_CACHE = None

def extract_models(text):
    """Extract model numbers from text (e.g. GA-F2A68HM-DS2, G43MX, K8V-X SE)."""
    if not text:
        return set()
    BRANDS = {"gigabyte", "foxconn", "asus", "intel", "amd", "nvidia", "kingston",
              "samsung", "dell", "hp", "lenovo", "a4tech", "logitech", "sony",
              "western", "seagate", "toshiba", "fujitsu", "hitachi", "liteon",
              "zalman", "benq", "philips", "sencor", "patriot", "lg", "nec",
              "brocade", "cisco", "finisar", "netgear", "nortel", "avaya",
              "infineon", "corus", "picolight", "jdsu", "adva", "agilent",
              "problabs", "d-link", "hp", "fujitsu", "ocz", "corsair"}
    models = set()
    # Model patterns: alphanumeric with dashes, >4 chars, containing digits
    for m in re.findall(r'\b[A-Za-z0-9][A-Za-z0-9\-\./]+[A-Za-z0-9]\b', text):
        low = m.lower()
        if len(m) >= 4 and low not in BRANDS and not low.isalpha():
            models.add(low)
    return models

def match_stock_items(analysis_text, category, params_text, top_n=3):
    """Try to match Gemini analysis results to stock items."""
    from difflib import SequenceMatcher

    index = load_stock_index()
    if not index:
        return []

    query_text = f"{analysis_text or ''} {params_text or ''}"
    query_models = extract_models(query_text)
    query_lower = query_text.lower()

    scores = []  # [(poradie, score, item)]

    for poradie, item in index.items():
        name = item.get("nazov", "").lower()
        cat = item.get("kategoria", "").lower()
        item_text = f"{name} {cat}"
        item_models = extract_models(item.get("nazov", ""))

        # 1) Exact model match (highest confidence)
        shared = query_models & item_models
        if shared:
            base = 0.85
            bonus = min(len(shared) * 0.1, 0.15)
            scores.append((poradie, base + bonus, item, "model"))
            continue

        # 2) Fuzzy name similarity
        ratio = SequenceMatcher(None, query_lower[:50], name[:50]).ratio()
        if ratio > 0.4:
            scores.append((poradie, ratio, item, "name"))

        # 3) Partial token match (e.g. "DDR3" in both query and item)
        query_tokens = set(re.findall(r'\b[a-z0-9]+\b', query_lower))
        item_tokens = set(re.findall(r'\b[a-z0-9]+\b', name))
        # Only count meaningful tokens (>=3 chars, not stopwords)
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

    # Deduplicate: keep highest score per poradie
    best_per_item = {}
    for poradie, score, item, method in scores:
        if poradie not in best_per_item or score > best_per_item[poradie][0]:
            best_per_item[poradie] = (score, item, method)

    # Sort by score descending, take top N with score >= 0.35
    ranked = sorted(best_per_item.items(), key=lambda x: -x[1][0])
    results = []
    for poradie, (score, item, method) in ranked:
        if score >= 0.35:
            results.append({
                "poradie": poradie,
                "score": round(score, 2),
                "method": method,
                "nazov": item.get("nazov", ""),
                "kategoria": item.get("kategoria", ""),
                "predajna_cena": item.get("predajna_cena", ""),
                "pocet": item.get("pocet", "1"),
                "photos_count": len(item.get("photos", [])),
                "stav": item.get("stav", "sklad"),
            })
        if len(results) >= top_n:
            break

    return results

# ── Category Templates ────────────────────────────────────────────

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

# ── Gemini Vision Helper ──────────────────────────────────────────

def get_gemini_api_key():
    env_path = os.path.join(os.path.dirname(os.path.dirname(BASE_DIR)), ".env")
    alt_path = os.path.join(os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes")), ".env")
    for p in [env_path, alt_path]:
        if os.path.exists(p):
            with open(p) as f:
                for line in f:
                    if line.startswith("GOOGLE_API_KEY=") and not line.startswith("#"):
                        return line.strip().split("=", 1)[1]
    return None

def analyze_image(image_b64):
    """Send image to Gemini and get structured analysis (fast)."""
    api_key = get_gemini_api_key()
    if not api_key:
        return {"error": "No Gemini API key"}, 0

    import time
    t0 = time.time()

    # Fast model + short prompt
    prompt = "Identify this tech item. Return JSON: {\"category\":\"RAM|Notebook|Monitor|Other\",\"description\":\"brief 1-line\",\"parameters\":{all detectable specs}}. Fill only what you see, empty strings for unknown."

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
        return {"error": "No JSON in response", "raw": text[:200]}, int((time.time() - t0) * 1000)
    except urllib.error.HTTPError as e:
        return {"error": f"API HTTP {e.code}: {e.read().decode()[:200]}"}, int((time.time() - t0) * 1000)
    except Exception as e:
        return {"error": str(e)}, int((time.time() - t0) * 1000)

def smart_filename(analysis, category):
    """Generate descriptive filename like hpprobook3456.jpg from analysis."""
    params = analysis.get("parameters", {})
    brand = (params.get("brand", "") or "").strip().lower()[:6]
    model = (params.get("model", "") or "").strip().lower()[:15]
    model = model.replace(" ", "").replace("-", "").replace("/", "")
    cap = params.get("capacity", "").lower().replace("gb", "").strip()[:4]
    speed = params.get("speed", "").lower().replace("mhz", "").strip()[:5]
    
    parts = []
    if brand:
        bmap = {"sk hynix": "hynix", "hewlett-packard": "hp", "hp": "hp",
                "dell": "dell", "lenovo": "lenovo", "samsung": "samsung",
                "kingston": "king", "apple": "apple", "asus": "asus", "acer": "acer"}
        parts.append(bmap.get(brand, brand[:4]))
    if model:
        parts.append(model[:12])
    if cap and speed:
        parts.append(f"{cap}gb{speed}")
    elif cap:
        parts.append(f"{cap}gb")
    
    if not parts:
        return None
    name = "_".join(parts).replace(" ", "_").replace("__", "_").strip("_")
    return name[:40]

def generate_advert(params, template):
    """Generate advert description from filled template."""
    api_key = get_gemini_api_key()
    
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

# ── HTTP Handler ──────────────────────────────────────────────────

class AdvertHandler(SimpleHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PUT, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Bypass-Tunnel-Reminder, X-Requested-With")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_POST(self):
        origin = self.headers.get("Origin", "*")
        if self.path == "/upload":
            self.handle_upload(origin)
        elif self.path == "/generate":
            self.handle_generate(origin)
        elif self.path == "/save":
            self.handle_save(origin)
        elif self.path == "/categories":
            self.handle_categories(origin)
        elif self.path == "/pair":
            self.handle_pair(origin)
        else:
            self.send_error(404)

    def do_GET(self):
        # Health check for Render
        if self.path in ("/", "/health"):
            self._json({"ok": True, "status": "alive", "service": "advert-generator"}, None)
            return
        if self.path.startswith("/uploads/"):
            fname = self.path[len("/uploads/"):]
            fpath = os.path.join(UPLOAD_DIR, fname)
            if os.path.exists(fpath):
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(os.path.getsize(fpath)))
                self.end_headers()
                with open(fpath, "rb") as f:
                    self.wfile.write(f.read())
                return
        super().do_GET()

    # ── Upload + Analyze ─────────────────────────────────
    def handle_upload(self, origin):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len)
        try:
            data = json.loads(body.decode("utf-8"))
        except:
            self._json({"ok": False, "error": "Bad JSON"}, origin)
            return

        photos_b64 = data.get("photos", [])
        if not photos_b64:
            self._json({"ok": False, "error": "No photos"}, origin)
            return

        photo_b64 = photos_b64[0]
        # Save the photo
        photo_id = uuid.uuid4().hex[:8]
        ts = datetime.now().isoformat()
        raw_b64 = photo_b64.split(",", 1)[1] if "," in photo_b64 else photo_b64
        fname = f"photo_{photo_id}.jpg"
        fpath = os.path.join(UPLOAD_DIR, fname)
        with open(fpath, "wb") as f:
            f.write(base64.b64decode(raw_b64))

        # Record in DB
        entry = {"id": photo_id, "filename": fname, "path": fpath, "timestamp": ts, "size_bytes": os.path.getsize(fpath)}
        photo_list = []
        if os.path.exists(PHOTOS_DB):
            try:
                with open(PHOTOS_DB) as f:
                    photo_list = json.load(f)
            except:
                photo_list = []
        photo_list.append(entry)
        with open(PHOTOS_DB, "w") as f:
            json.dump(photo_list, f, indent=2)

        # Analyze with Gemini
        t0 = __import__('time').time()
        analysis, gemini_ms = analyze_image(photo_b64)
        total_ms = int((__import__('time').time() - t0) * 1000)

        if "error" in analysis:
            self._json({"ok": False, "error": analysis["error"], "timing": {"gemini_ms": gemini_ms, "total_ms": total_ms}}, origin)
            return

        category = analysis.get("category", "Other")
        if category not in TEMPLATES:
            category = "Other"

        # Smart rename based on analysis
        smart_name = smart_filename(analysis, category)
        if smart_name:
            new_fname = f"{smart_name}.jpg"
            new_fpath = os.path.join(UPLOAD_DIR, new_fname)
            # Avoid overwriting existing files
            counter = 1
            while os.path.exists(new_fpath):
                new_fname = f"{smart_name}_{counter}.jpg"
                new_fpath = os.path.join(UPLOAD_DIR, new_fname)
                counter += 1
            os.rename(fpath, new_fpath)
            fname = new_fname
            fpath = new_fpath
            entry["filename"] = fname
            entry["path"] = fpath
            # Update DB
            photo_list[-1] = entry
            with open(PHOTOS_DB, "w") as f:
                json.dump(photo_list, f, indent=2)

        # Save extra photos with same base name
        base_name = os.path.splitext(fname)[0]  # e.g. "hynix_32gb1333" or "photo_abc123"
        all_entries = [entry]
        for i, extra_b64 in enumerate(photos_b64[1:], start=2):
            extra_fn = f"{base_name}_{i}.jpg"
            extra_fp = os.path.join(UPLOAD_DIR, extra_fn)
            raw = extra_b64.split(",", 1)[1] if "," in extra_b64 else extra_b64
            with open(extra_fp, "wb") as f:
                f.write(base64.b64decode(raw))
            extra_entry = {"id": uuid.uuid4().hex[:8], "filename": extra_fn, "path": extra_fp,
                           "timestamp": ts, "size_bytes": os.path.getsize(extra_fp)}
            photo_list.append(extra_entry)
            all_entries.append(extra_entry)
        with open(PHOTOS_DB, "w") as f:
            json.dump(photo_list, f, indent=2)

        template = TEMPLATES[category]
        params = analysis.get("parameters", {})

        # Map vision params to template fields
        filled = {}
        for field in template["fields"]:
            k = field["key"]
            val = params.get(k, params.get(field["label"].lower(), ""))
            if not val:
                val = field.get("default", "")
            filled[k] = val

        # ── Stock matching ─────────────────────────────────
        params_text = " ".join(f"{k}:{v}" for k, v in params.items() if v)
        matches = match_stock_items(
            analysis_text=analysis.get("description", ""),
            category=category,
            params_text=params_text,
            top_n=3,
        )
        match_status = "matched" if matches else "none"

        result = {
            "ok": True,
            "status": "complete",
            "category": category,
            "emoji": template["emoji"],
            "fields": template["fields"],
            "filled": filled,
            "description": analysis.get("description", ""),
            "photo": entry,
            "photos": all_entries,
            "matches": matches,
            "match_status": match_status,
            "timing": {"gemini_ms": gemini_ms, "total_ms": total_ms},
        }
        self._json(result, origin)

    # ── Generate Advert ──────────────────────────────────
    def handle_generate(self, origin):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len)
        try:
            data = json.loads(body.decode("utf-8"))
        except:
            self._json({"ok": False, "error": "Bad JSON"}, origin)
            return

        category = data.get("category", "Other")
        params = data.get("params", {})
        params["_category"] = category

        if category in TEMPLATES:
            advert = generate_advert(params, TEMPLATES[category])
        else:
            advert = {"description": "No template available", "source": "none"}

        self._json({"ok": True, "description": advert["description"], "source": advert["source"]}, origin)

    # ── Save Advert ───────────────────────────────────────
    def handle_save(self, origin):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len)
        try:
            data = json.loads(body.decode("utf-8"))
        except:
            self._json({"ok": False, "error": "Bad JSON"}, origin)
            return

        advert_id = uuid.uuid4().hex[:12]
        ts = datetime.now().isoformat()
        record = {
            "id": advert_id,
            "timestamp": ts,
            "category": data.get("category"),
            "params": data.get("params", {}),
            "description": data.get("description", ""),
            "photo": data.get("photo"),
        }

        fpath = os.path.join(ADVERTS_DIR, f"advert_{advert_id}.json")
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)

        self._json({"ok": True, "id": advert_id, "path": fpath, "message": "Advert saved!"}, origin)

    # ── List Categories ───────────────────────────────────
    def handle_categories(self, origin):
        cats = {k: {"emoji": v["emoji"], "fields": v["fields"]} for k, v in TEMPLATES.items()}
        self._json({"ok": True, "categories": cats}, origin)

    # ── Pair photo with stock item ─────────────────────────
    def handle_pair(self, origin):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len)
        try:
            data = json.loads(body.decode("utf-8"))
        except:
            self._json({"ok": False, "error": "Bad JSON"}, origin)
            return

        poradie = str(data.get("poradie", ""))
        action = data.get("action", "pair")  # 'pair' or 'increase'
        photo = data.get("photo", {})
        description = data.get("description", "")

        if not poradie:
            self._json({"ok": False, "error": "Missing poradie"}, origin)
            return

        # Load and update index
        index = load_stock_index()
        if poradie not in index:
            self._json({"ok": False, "error": f"Item #{poradie} not found"}, origin)
            return

        item = index[poradie]

        if action == "pair":
            # Add photo reference
            if photo and photo.get("filename"):
                photo_ref = {
                    "file": photo["filename"],
                    "path": "(uploaded)",
                    "id": photo.get("id", ""),
                }
                if "photos" not in item:
                    item["photos"] = []
                # Avoid duplicates
                if photo_ref not in item["photos"]:
                    item["photos"].append(photo_ref)

            # Update stav
            item["stav"] = "nafotené"
            item["last_check"] = str(datetime.now().date())
            item["poznamky"] = (item.get("poznamky", "") + f"; {description}" if description and description not in item.get("nazov", "") else item.get("poznamky", ""))
            msg = f"Photo paired with #{poradie} ({item['nazov']})"

        elif action == "increase":
            # Increase quantity
            current_qty = int(item.get("pocet", "1") or "1")
            item["pocet"] = str(current_qty + 1)
            item["last_check"] = str(datetime.now().date())
            msg = f"Count increased for #{poradie}: {current_qty} → {current_qty + 1}"

        else:
            self._json({"ok": False, "error": f"Unknown action: {action}"}, origin)
            return

        # Write updated index
        with open(INDEX_PATH, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
        invalidate_stock_cache()

        # Also try to update Google Sheets (silently if it fails)
        try:
            sys.path.insert(0, os.path.join(HERMES_HOME, "skills/productivity/google-workspace/scripts"))
            from google_api import build_service
            service = build_service("sheets", "v4")

            row_num = int(poradie) + 1  # +1 for header
            if action == "pair" and photo.get("filename"):
                # Could add photo URL to a notes column
                pass

            # Update pocet (column D) if increased
            if action == "increase":
                service.spreadsheets().values().update(
                    spreadsheetId=SHEET_ID,
                    range=f"D{row_num}",
                    valueInputOption="USER_ENTERED",
                    body={"values": [[item["pocet"]]]}
                ).execute()

            self._json({"ok": True, "message": msg, "poradie": poradie, "item": {
                "nazov": item.get("nazov", ""),
                "pocet": item.get("pocet", "1"),
                "photos_count": len(item.get("photos", [])),
                "stav": item.get("stav", "sklad"),
            }}, origin)
        except Exception as e:
            # Still succeed — index is updated locally
            self._json({"ok": True, "message": msg + " (Sheet sync skipped)", "poradie": poradie, "item": {
                "nazov": item.get("nazov", ""),
                "pocet": item.get("pocet", "1"),
                "photos_count": len(item.get("photos", [])),
                "stav": item.get("stav", "sklad"),
            }}, origin)

    def _json(self, obj, origin):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # quiet


def main():
    port = int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) > 1 else 8080))
    server = HTTPServer(("0.0.0.0", port), AdvertHandler)
    print(f"🚀 Advert Generator Server on :{port}")
    print(f"📁 Uploads: {UPLOAD_DIR if os.path.exists(UPLOAD_DIR) else 'disabled'}")
    print(f"📁 Adverts: {ADVERTS_DIR if os.path.exists(ADVERTS_DIR) else 'disabled'}")
    print(f"🔑 Gemini key: {'found' if get_gemini_api_key() else 'MISSING'}")
    stock_count = len(load_stock_index())
    print(f"📦 Stock index: {stock_count} items ({INDEX_PATH})")
    server.serve_forever()

if __name__ == "__main__":
    main()
