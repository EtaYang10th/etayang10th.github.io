#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "scholar.json"
JS_DATA_PATH = ROOT / "data" / "scholar.js"
SCHOLAR_USER_ID = os.environ.get("SCHOLAR_USER_ID", "BsQ8IUcAAAAJ")
SCHOLAR_URL = f"https://scholar.google.com/citations?user={SCHOLAR_USER_ID}&hl=en"
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def load_existing_payload() -> dict:
    if not DATA_PATH.exists():
        return {}

    try:
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def fetch_scholar_html(url: str) -> str:
    req = request.Request(url, headers=REQUEST_HEADERS)
    with request.urlopen(req, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def parse_citation_count(html: str) -> int:
    table_match = re.search(
        r'<table[^>]*id=["\']gsc_rsb_st["\'][^>]*>(.*?)</table>',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    search_scope = table_match.group(1) if table_match else html

    values = re.findall(
        r'<td[^>]*class=["\'][^"\']*gsc_rsb_std[^"\']*["\'][^>]*>\s*([^<]+?)\s*</td>',
        search_scope,
        re.IGNORECASE | re.DOTALL,
    )
    if not values:
        raise ValueError("Could not find Google Scholar metrics table.")

    digits = re.sub(r"[^\d]", "", values[0])
    if not digits:
        raise ValueError("Citation count field did not contain digits.")

    return int(digits)


def build_payload(citations: int) -> dict:
    return {
        "citations": citations,
        "scholar_url": SCHOLAR_URL,
        "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": "Google Scholar",
    }


def write_payload(payload: dict) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    js_payload = "window.__SCHOLAR_CACHE__ = " + json.dumps(payload, indent=2) + ";\n"
    JS_DATA_PATH.write_text(js_payload, encoding="utf-8")


def main() -> int:
    existing_payload = load_existing_payload()

    try:
        html = fetch_scholar_html(SCHOLAR_URL)
        citations = parse_citation_count(html)
    except (error.URLError, TimeoutError, ValueError) as exc:
        if DATA_PATH.exists():
            print(f"Warning: failed to refresh Google Scholar cache: {exc}")
            print("Keeping the existing cached JSON file unchanged.")
            return 0

        print(f"Error: failed to fetch citation count and no cache exists yet: {exc}", file=sys.stderr)
        return 1

    payload = build_payload(citations)
    if payload == existing_payload:
        print(f"Citation count unchanged at {citations}.")
        return 0

    write_payload(payload)
    print(f"Updated scholar cache with {citations} citations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
