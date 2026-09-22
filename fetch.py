#!/usr/bin/env python3
"""Fetch every source in sources.json and write a stable-fingerprint snapshot.json."""

import datetime
import hashlib
import json
import os
import re
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
UA = "psp-drift-watch/0.2 (+https://github.com/PayIntLab)"


def _get_json(url: str, accept=None):
    headers = {"User-Agent": UA}
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def _get_http(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8", "replace")
        info = resp.info()
        return body, {
            "etag": info.get("ETag"),
            "last_modified": info.get("Last-Modified"),
            "status": resp.status,
        }


_DYNAMIC_PATTERNS = [
    re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\b\d{2}:\d{2}:\d{2}\b"),
    re.compile(r"\b\d+\s+(?:second|minute|hour|day|week|month|year)s?\s+ago\b", re.I),
    re.compile(r"\b(?:just now|yesterday|today|ago)\b", re.I),
    re.compile(r"\b[0-9a-f]{32,}\b", re.I),
]


def normalize(body: str) -> str:
    b = body
    for p in _DYNAMIC_PATTERNS:
        b = p.sub(" ", b)
    return re.sub(r"\s+", " ", b).strip()


def collect(s: dict) -> dict:
    kind = s["kind"]
    if kind == "github_commits":
        q = "?per_page=1"
        if s.get("path"):
            q += f"&path={s['path']}"
        data = _get_json(
            f"https://api.github.com/repos/{s['repo']}/commits{q}",
            "application/vnd.github+json",
        )
        if isinstance(data, list) and data:
            c = data[0]
            msg = c["commit"]["message"].split("\n")[0][:80]
            return {
                "ok": True,
                "fingerprint": c["sha"],
                "detail": f"{c['sha'][:8]} {c['commit']['committer']['date']} | {msg}",
            }
        return {"ok": False, "error": "no commits returned"}

    if kind == "github_releases":
        data = _get_json(
            f"https://api.github.com/repos/{s['repo']}/releases/latest",
            "application/vnd.github+json",
        )
        tag = data.get("tag_name")
        if tag:
            return {
                "ok": True,
                "fingerprint": tag,
                "detail": f"{tag} ({data.get('published_at', '')})",
            }
        return {"ok": False, "error": "no latest release"}

    if kind == "devto_api":
        data = _get_json(f"https://dev.to/api/articles/{s['username']}/{s['slug']}")
        return {
            "ok": True,
            "fingerprint": data.get("edited_at") or data.get("published_at"),
            "detail": data.get("title", ""),
        }

    if kind == "http":
        body, meta = _get_http(s["url"])
        fp = meta.get("etag") or hashlib.sha256(normalize(body).encode("utf-8")).hexdigest()
        return {
            "ok": True,
            "fingerprint": fp,
            "detail": f"etag={meta.get('etag')} last-modified={meta.get('last_modified')} size={len(body)}",
        }

    return {"ok": False, "error": f"unknown kind: {kind}"}


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
            "kind": s["kind"],
            "signal": s["signal"],
        }
        try:
            entry.update(collect(s))
        except Exception as e:  # noqa: BLE001
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
