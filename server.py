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
        return {"error": "No Gemini API key"}

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
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return {"error": "No JSON in response", "raw": text[:200]}
    except urllib.error.HTTPError as e:
        return {"error": f"API HTTP {e.code}: {e.read().decode()[:200]}"}
    except Exception as e:
        return {"error": str(e)}

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
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
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
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
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
        else:
            self.send_error(404)

    def do_GET(self):
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
        self._json({"ok": True, "status": "analyzing", "photo": entry, "message": "Analyzing photo..."}, origin)

        analysis = analyze_image(photo_b64)

        if "error" in analysis:
            self._json({"ok": False, "error": analysis["error"]}, origin)
            return

        category = analysis.get("category", "Other")
        if category not in TEMPLATES:
            category = "Other"

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

        result = {
            "ok": True,
            "status": "complete",
            "category": category,
            "emoji": template["emoji"],
            "fields": template["fields"],
            "filled": filled,
            "description": analysis.get("description", ""),
            "photo": entry,
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
    server.serve_forever()

if __name__ == "__main__":
    main()
