"""Refresh data/red-folder.json: the US high impact (red folder) events for
this week and next, from the ForexFactory calendar feed.

Runs inside GitHub Actions on the public site repo. Standard library only.

This week's feed is the one that matters: if it fails (after one retry), the
last good file stays, so the page never goes blank. Next week's feed is a bonus:
it answered 404 on 2026-10-05, so when it is missing or fails, this week is still
refreshed and the next week events already stored from an earlier run are kept,
never dropped. A 404 is not retried; a missing file will not appear in 30 seconds.

    python .github/scripts/red_folder.py            # fetch and write
    RF_FEED_FILE=sample.json python ...              # read a local file instead (testing)
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

THIS_WEEK = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
NEXT_WEEK = "https://nfs.faireconomy.media/ff_calendar_nextweek.json"
OUT = os.path.join("data", "red-folder.json")
UA = "fnptrades.com red folder calendar (github actions)"
RETRY_WAIT = 30  # seconds before a feed's one retry (the feed rate limits)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_retry(url):
    """The feed's rows, or None when it fails twice or is missing (404)."""
    for attempt in (1, 2):
        try:
            return fetch(url)
        except (OSError, ValueError) as e:  # network errors, HTTP errors, a non JSON "request denied" page
            print(f"warning: {url} (attempt {attempt}): {e}", file=sys.stderr)
            if getattr(e, "code", None) == 404:
                return None
            if attempt == 1:
                time.sleep(RETRY_WAIT)
    return None


def when(date):
    return datetime.fromisoformat(date)


def red_folder(rows):
    """USD high impact rows as events, deduplicated."""
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
    return events


def main():
    local = os.environ.get("RF_FEED_FILE")
    if local:
        this, nxt = json.load(open(local, encoding="utf-8")), []
    else:
        this = fetch_retry(THIS_WEEK)
        if this is None:
            print("this week's feed failed, keeping the last good file", file=sys.stderr)
            return 0
        nxt = fetch_retry(NEXT_WEEK)

    old = None
    if os.path.exists(OUT):
        try:
            old = json.load(open(OUT, encoding="utf-8"))
        except ValueError:
            old = None

    events = red_folder(this + (nxt or []))
    if nxt is None and old:
        # next week's feed is missing: keep the stored events that fall after this week's feed
        dates = [when(r["date"]) for r in this if r.get("date")]
        week_end = max(dates) if dates else datetime.now(timezone.utc)
        have = {(e["title"], e["date"]) for e in events}
        kept = [e for e in old.get("events", [])
                if when(e["date"]) > week_end and (e["title"], e["date"]) not in have]
        events += kept
        print(f"next week's feed missing, kept {len(kept)} stored next week events", file=sys.stderr)
    events.sort(key=lambda e: when(e["date"]))

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
