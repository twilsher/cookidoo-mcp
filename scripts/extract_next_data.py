#!/usr/bin/env python3
"""Extract __NEXT_DATA__ blobs from HAR HTML responses and dump them to JSON files."""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

HAR = Path(sys.argv[1])
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)

d = json.loads(HAR.read_text())
for i, e in enumerate(d["log"]["entries"]):
    body = (e["response"].get("content") or {}).get("text", "") or ""
    mime = (e["response"].get("content") or {}).get("mimeType", "")
    u = urlparse(e["request"]["url"])
    if u.netloc != "cookidoo.international" or "html" not in mime or len(body) < 5000:
        continue
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', body, re.DOTALL)
    if not m:
        continue
    try:
        nd = json.loads(m.group(1))
    except Exception as ex:
        print(f"skip {u.path}: {ex}", file=sys.stderr)
        continue
    slug = u.path.strip("/").replace("/", "__") or "root"
    out = OUT / f"{slug}.json"
    out.write_text(json.dumps(nd, indent=2, ensure_ascii=False))
    print(f"{u.path} -> {out} ({out.stat().st_size} bytes)")
