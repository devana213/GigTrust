"""Mongo activity-log proof: writes a test event through the API, then reads the log back.

Run from C:\\Dev\\GigTrust (backend server must be running):
    .venv312\\Scripts\\python.exe mongo_check.py
"""
import json
import os
import urllib.request
from collections import Counter

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

BASE = "http://127.0.0.1:8000"

print("[1] POST /activity/test")
req = urllib.request.Request(f"{BASE}/activity/test", method="POST")
with urllib.request.urlopen(req, timeout=60) as r:
    print(r.read().decode())

client = MongoClient(os.getenv("MONGO_URI"), directConnection=True, tls=True,
                     serverSelectionTimeoutMS=20000)
coll = client[os.getenv("MONGO_DATABASE")][os.getenv("MONGO_COLLECTION")]

docs = list(coll.find().sort("_id", -1).limit(200))
print(f"\n[2] Documents read back (latest 200 max): {len(docs)}")

counts = Counter(d.get("event_type", "?") for d in docs)
print("\n[3] Event counts by type:")
for k, v in counts.most_common():
    print(f"    {k}: {v}")

print("\n[4] Newest 5 documents (raw):")
for d in docs[:5]:
    d.pop("_id", None)
    print("   ", json.dumps(d, default=str))
