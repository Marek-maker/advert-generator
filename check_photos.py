#!/usr/bin/env python3
"""Check for newly uploaded photos from the Mini App."""
import json, os, sys

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "_received.json")

if not os.path.exists(DB):
    print("No photos uploaded yet.")
    sys.exit(0)

with open(DB) as f:
    photos = json.load(f)

unseen = [p for p in photos if not p.get("seen", False)]

if not unseen:
    print(f"No new photos. Total archive: {len(photos)}")
else:
    for p in unseen:
        print(f"📸 {p['filename']} ({p['size_bytes']/1024:.1f}KB @ {p['timestamp']})")
        print(f"   Path: {p['path']}")
    print(f"\nTotal: {len(unseen)} new photo(s)")

# Mark as seen
for p in photos:
    p["seen"] = True
with open(DB, "w") as f:
    json.dump(photos, f, indent=2)
