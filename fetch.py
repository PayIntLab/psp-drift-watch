#!/usr/bin/env python3
"""Fetch every source in sources.json and write a normalized snapshot.json."""

import datetime
import hashlib
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
UA = "psp-drift-watch/0.1 (+https://github.com/PayIntLab)"


def fetch(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8", "replace")
        info = resp.info()
        return {
            "status": resp.status,
            "etag": info.get("ETag"),
            "last_modified": info.get("Last-Modified"),
            "content_type": info.get("Content-Type"),
            "body": body,
        }


def normalize(body: str) -> str:
    return re.sub(r"\s+", " ", body).strip()


def extract_title(body: str):
    m = re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else None


def main():
    with open(os.path.join(ROOT, "sources.json"), encoding="utf-8") as f:
        cfg = json.load(f)

    snapshot = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "sources": {},
    }

    for s in cfg["sources"]:
        entry = {
            "platform": s["platform"],
            "name": s["name"],
            "url": s["url"],
            "kind": s["kind"],
            "signal": s["signal"],
        }
        try:
            r = fetch(s["url"])
            norm = normalize(r["body"])
            entry.update(
                {
                    "ok": True,
                    "status": r["status"],
                    "etag": r["etag"],
                    "last_modified": r["last_modified"],
                    "title": extract_title(r["body"]),
                    "sha256": hashlib.sha256(norm.encode("utf-8")).hexdigest(),
                    "size": len(norm),
                }
            )
        except Exception as e:  # noqa: BLE001 - record failure without aborting
            entry.update({"ok": False, "error": f"{type(e).__name__}: {e}"})
        snapshot["sources"][s["id"]] = entry

    out = os.path.join(ROOT, "snapshot.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    ok = sum(1 for e in snapshot["sources"].values() if e.get("ok"))
    total = len(snapshot["sources"])
    print(f"wrote {out}: {ok}/{total} sources fetched")
    if ok < total:
        print("failed sources:", [i for i, e in snapshot["sources"].items() if not e.get("ok")])


if __name__ == "__main__":
    main()
