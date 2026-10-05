"""Refresh data/red-folder.json: the US high impact (red folder) events for
this week and next, from the ForexFactory calendar feed.

Runs inside GitHub Actions on the public site repo. Standard library only.
Keeps the last good file when the feed is unreachable, so the page never
goes blank because of one failed fetch.

    python .github/scripts/red_folder.py            # fetch and write
    RF_FEED_FILE=sample.json python ...              # read a local file instead (testing)
"""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

FEEDS = [
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    "https://nfs.faireconomy.media/ff_calendar_nextweek.json",
]
OUT = os.path.join("data", "red-folder.json")
UA = "fnptrades.com red folder calendar (github actions)"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def load():
    local = os.environ.get("RF_FEED_FILE")
    if local:
        return json.load(open(local, encoding="utf-8")), 1
    rows, ok = [], 0
    for url in FEEDS:
        try:
            rows += fetch(url)
            ok += 1
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, TimeoutError) as e:
            print(f"warning: {url}: {e}", file=sys.stderr)
    return rows, ok


def main():
    rows, ok = load()
    if not ok:
        print("feed unreachable, keeping the last good file", file=sys.stderr)
        return 0
    seen, events = set(), []
    for r in rows:
        if str(r.get("country", "")).upper() != "USD" or str(r.get("impact", "")).lower() != "high":
            continue
        key = (r.get("title", ""), r.get("date", ""))
        if key in seen or not r.get("date"):
            continue
        seen.add(key)
        events.append({"title": r.get("title", "").strip(), "date": r["date"],
                       "forecast": (r.get("forecast") or "").strip(),
                       "previous": (r.get("previous") or "").strip()})
    events.sort(key=lambda e: e["date"])
    old = None
    if os.path.exists(OUT):
        try:
            old = json.load(open(OUT, encoding="utf-8"))
        except ValueError:
            old = None
    if old and old.get("events") == events:
        print(f"no change ({len(events)} events)")
        return 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    doc = {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "source": "ForexFactory calendar, USD, high impact", "events": events}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")
    print(f"wrote {OUT}: {len(events)} events")
    return 0


if __name__ == "__main__":
    sys.exit(main())
