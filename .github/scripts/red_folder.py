"""Refresh data/red-folder.json: the US high impact (red folder) events for
this week and next, from the ForexFactory calendar feed.

Runs inside GitHub Actions on the public site repo. Standard library only.
Writes only when both weeks' feeds come back (each gets one retry). If either
fails, the last good file stays, so a half fetched calendar (this week without
next week) never replaces a complete one and the page never goes blank.

    python .github/scripts/red_folder.py            # fetch and write
    RF_FEED_FILE=sample.json python ...              # read a local file instead (testing)
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

FEEDS = [
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    "https://nfs.faireconomy.media/ff_calendar_nextweek.json",
]
OUT = os.path.join("data", "red-folder.json")
UA = "fnptrades.com red folder calendar (github actions)"
RETRY_WAIT = 30  # seconds before a feed's one retry (the feed rate limits)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def load():
    """All rows, and whether every feed came back."""
    local = os.environ.get("RF_FEED_FILE")
    if local:
        return json.load(open(local, encoding="utf-8")), True
    rows, complete = [], True
    for url in FEEDS:
        for attempt in (1, 2):
            try:
                rows += fetch(url)
                break
            except (OSError, ValueError) as e:  # network errors, HTTP errors, a non JSON "request denied" page
                print(f"warning: {url} (attempt {attempt}): {e}", file=sys.stderr)
                if attempt == 1:
                    time.sleep(RETRY_WAIT)
        else:
            complete = False
    return rows, complete


def main():
    rows, complete = load()
    if not complete:
        print("a feed failed, keeping the last good file", file=sys.stderr)
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
