"""Several posts about the SAME event (same club, date, time and place) become ONE event.
The earliest post gives the title/description; the picture comes from the earliest STILL post
(reels are only used when there is no still picture)."""
import re
from difflib import SequenceMatcher


def _place(ev):
    loc = ev.get("location")
    return re.sub(r"[^a-z0-9]", "", (loc["text"] if loc else "").lower())


def _same(a, b):
    if a["club"]["handle"] != b["club"]["handle"]:
        return False
    if a["start"][:10] != b["start"][:10]:                      # same calendar day...
        return False
    if a["start"] != b["start"] and not (a["date_only"] or b["date_only"]):   # ...and same time (unless a time is missing)
        return False
    pa, pb = _place(a), _place(b)
    return not pa or not pb or pa in pb or pb in pa             # same place (or a place is missing)


def _choose_image(ev):
    """Earliest still picture, else earliest picture of any kind."""
    members = sorted((m for m in ev["posts"] if m.get("image")), key=lambda m: m["posted_at"])
    best = next((m for m in members if not m["is_reel"]), members[0] if members else None)
    for m in ev["posts"]:                    # keep only the chosen file; the others get deleted by the cleanup
        if m is not best:
            m["image"] = None
    ev["image"], ev["is_reel"] = (best["image"], best["is_reel"]) if best else (None, False)


def _absorb(a, b):
    """a = earlier post's event (kept), b = later duplicate."""
    known = {m["id"] for m in a["posts"]}
    a["posts"] += [m for m in b["posts"] if m["id"] not in known]
    if a["date_only"] and not b["date_only"]:                   # the other post knows the time
        for k in ("start", "end", "duration_min", "date_only"):
            a[k] = b[k]
    if not a.get("location") and b.get("location"):
        a["location"] = b["location"]
    if a["cost"]["type"] == "unknown" and b["cost"]["type"] != "unknown":
        a["cost"] = b["cost"]
    a["rsvp_required"] = a["rsvp_required"] or b["rsvp_required"]
    a["dependency"] = a.get("dependency") or b.get("dependency")
    a["recurrence"] = a.get("recurrence") or b.get("recurrence")
    if b["status"] == "cancelled":
        a["status"] = "cancelled"
    a["updates"] += b["updates"]
    # one post in English + another in French -> the event is bilingual, each language uses its own post
    if set(a["languages"]) != {"en", "fr"} and a["languages"] and b["languages"] and set(a["languages"]) != set(b["languages"]):
        lb = b["languages"][0]
        if len(b["languages"]) == 1:
            a["title"][lb], a["description"][lb] = b["title"][lb], b["description"][lb]
            a["languages"], a["language_note"], a["translated_from"] = ["en", "fr"], None, None
    _choose_image(a)


def merge_events(events):
    """events: {id: event}. Returns a new dict with duplicates merged."""
    out = []
    for e in sorted(events.values(), key=lambda e: e["posted_at"]):
        if not e.get("posts"):
            e["posts"] = [{"id": e["id"], "url": e["post_url"], "posted_at": e["posted_at"],
                           "is_reel": e.get("is_reel", False), "image": e.get("image")}]
        target = next((p for p in out if _same(p, e)), None)
        if target:
            _absorb(target, e)
        else:
            out.append(e)
    return {e["id"]: e for e in out}
