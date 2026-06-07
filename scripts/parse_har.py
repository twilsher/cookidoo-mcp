#!/usr/bin/env python3
"""Parse a Cookidoo HAR capture into an endpoint inventory.

Filters out static assets (js/css/img/font) and third-party telemetry, then
groups by (METHOD, path-template) where the template abstracts ULIDs, numeric
IDs, r-prefixed recipe IDs, and language codes.
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse, parse_qsl

HAR = Path(sys.argv[1] if len(sys.argv) > 1 else "captures/cookidoo-2026-05-22.har")

# Hosts that matter for API discovery. Everything else is page/asset/telemetry.
API_HOSTS = re.compile(
    r"(cookidoo\.international|tmmobile\.vorwerk-digital\.com|"
    r"api\.cookidoo|vorwerk\.com/ciam|login\.vorwerk\.com)",
    re.I,
)
ASSET_EXT = re.compile(r"\.(js|css|woff2?|ttf|otf|png|jpe?g|gif|svg|webp|ico|map)(\?|$)", re.I)
STATIC_PATH = re.compile(r"/(static|assets|_next/static|cdn-cgi|images|fonts)/", re.I)
TELEMETRY = re.compile(
    r"(google-analytics|googletagmanager|doubleclick|hotjar|datadog|sentry|"
    r"segment|onetrust|cookielaw|optimizely|newrelic|cdn\.cookielaw)",
    re.I,
)

ULID = re.compile(r"\b[0-9A-HJKMNP-TV-Z]{26}\b")
R_RECIPE = re.compile(r"\br\d{4,}\b")
NUM_ID = re.compile(r"/\d{3,}(?=/|$)")
LANG_SEG = re.compile(r"/(en|no|nb|de|fr|es|it|nl|pl|pt|cs|sv|da|fi)(?=/|$)", re.I)


def templatize(path: str) -> str:
    p = LANG_SEG.sub("/{lang}", path)
    p = ULID.sub("{ulid}", p)
    p = R_RECIPE.sub("{recipe_id}", p)
    p = NUM_ID.sub("/{id}", p)
    return p


def short(s, n=200):
    if s is None:
        return None
    s = s.strip()
    return s if len(s) <= n else s[:n] + "…"


def is_interesting(req_url: str, mime: str) -> bool:
    if TELEMETRY.search(req_url):
        return False
    if ASSET_EXT.search(req_url):
        return False
    if STATIC_PATH.search(req_url):
        return False
    if not API_HOSTS.search(req_url):
        return False
    # Skip HTML page documents — they're not API endpoints.
    if mime and "text/html" in mime:
        return False
    return True


def main():
    data = json.loads(HAR.read_text())
    entries = data["log"]["entries"]
    print(f"# parsed {len(entries)} entries from {HAR.name}", file=sys.stderr)

    # group: (method, host, template) -> list of (full_path, status, mime, req_body_sample, resp_body_sample, req_headers_oi)
    groups = defaultdict(list)
    auth_hits = []

    for e in entries:
        req = e["request"]
        res = e["response"]
        url = req["url"]
        mime = (res.get("content") or {}).get("mimeType", "")
        if not is_interesting(url, mime):
            continue
        u = urlparse(url)
        tmpl = templatize(u.path)
        key = (req["method"], u.netloc, tmpl)

        # Pick interesting request headers
        hdrs = {h["name"].lower(): h["value"] for h in req.get("headers", [])}
        oi_headers = {
            k: hdrs.get(k)
            for k in ["authorization", "x-tm-api-key", "x-tenant", "accept", "content-type", "accept-language"]
            if hdrs.get(k)
        }
        if oi_headers.get("authorization"):
            oi_headers["authorization"] = oi_headers["authorization"][:25] + "…(redacted)"

        # Body samples
        req_body = None
        if req.get("postData"):
            req_body = req["postData"].get("text") or ""
        resp_body = (res.get("content") or {}).get("text") or ""

        groups[key].append({
            "path": u.path,
            "query": dict(parse_qsl(u.query)),
            "status": res["status"],
            "mime": mime,
            "req_headers": oi_headers,
            "req_body": short(req_body, 400) if req_body else None,
            "resp_body": short(resp_body, 600),
            "resp_size": len(resp_body),
        })

        # Track auth-relevant flows separately
        if re.search(r"/(token|oauth|authorize|login|signin|ciam|callback|refresh)", u.path, re.I):
            auth_hits.append({
                "method": req["method"],
                "host": u.netloc,
                "path": u.path,
                "status": res["status"],
                "query_keys": list(dict(parse_qsl(u.query)).keys()),
                "req_body": short(req_body, 300) if req_body else None,
            })

    # Emit
    print(f"# Cookidoo HAR endpoint inventory")
    print(f"# source: {HAR}")
    print(f"# entries: {len(entries)} total, {sum(len(v) for v in groups.values())} kept")
    print()
    print(f"## Auth flow hits ({len(auth_hits)})")
    for a in auth_hits:
        print(f"- {a['method']} {a['host']}{a['path']} -> {a['status']}  qs={a['query_keys']}")
        if a["req_body"]:
            print(f"    body: {a['req_body']}")
    print()
    print(f"## API endpoints (grouped by method + path template)")
    for (method, host, tmpl), calls in sorted(groups.items(), key=lambda x: (x[0][1], x[0][2], x[0][0])):
        first = calls[0]
        print(f"\n### {method} {host}{tmpl}  ({len(calls)} call{'s' if len(calls)!=1 else ''})")
        # show one example path
        print(f"- example: {first['path']}")
        if first["query"]:
            print(f"- query keys: {list(first['query'].keys())}")
        statuses = sorted({c['status'] for c in calls})
        print(f"- status: {statuses}")
        if first["mime"]:
            print(f"- response mime: {first['mime']}")
        if first["req_headers"]:
            print(f"- request headers of note: {first['req_headers']}")
        if first["req_body"]:
            print(f"- request body sample: {first['req_body']}")
        if first["resp_body"]:
            print(f"- response sample ({first['resp_size']} bytes): {first['resp_body']}")


if __name__ == "__main__":
    main()
