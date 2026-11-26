"""Follow-up posts: only link them to an event when they contain a clear keyword
(cancelled / rescheduled / room change)."""
import re
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher

from . import dates, details

KINDS = [
    ("cancelled", re.compile(r"\bcancell?ed\b|\bcancell?ation\b|\bannule\w*|\bannulation\b")),
    ("location", re.compile(r"\broom change\b|\blocation change\b|\bvenue change\b|\bnew (?:room|location|venue)\b|"
                            r"\bchangement de (?:salle|local|lieu)\b|\bnouvelle salle\b|\bnouveau (?:local|lieu)\b")),
    ("rescheduled", re.compile(r"\breschedul\w*|\bpostpon\w*|\breporte\w*|\bnew date\b|\bnouvelle date\b|\bmoved to\b|"
                               r"\btime change\b|\bchangement d'?horaire\b")),
]
STOP = {"this", "that", "with", "from", "have", "will", "your", "event", "tonight", "today", "sorry", "pour", "nous", "vous", "cette"}


def find_kind(t):
    for kind, rx in KINDS:
        if rx.search(t):
            return kind
    return None


def _tokens(s):
    return {w for w in re.findall(r"[a-z]{4,}", dates.norm(s)) if w not in STOP}


def match_event(events, post, t, ref, now):
    """Best existing event of the SAME club, or None."""
    cands = [e for e in events.values()
             if e["club"]["handle"] == post.handle and e["platform"] == post.platform
             and e["status"] == "active" and e["id"] != f"{post.platform}:{post.post_id}"]
    near = [e for e in cands if now - timedelta(days=1) <= datetime.fromisoformat(e["start"]) <= now + timedelta(days=14)]
    mentioned = {h.start for h in dates.find_dates(t, ref)}
    best, best_score = None, 0.0
    for e in cands:
        title = dates.norm(e["title"]["en"])
        score = max(SequenceMatcher(None, dates.norm(details.guess_title(post.caption, "")), title).ratio(),
                    min(1.0, 0.3 * len(_tokens(t) & _tokens(title))))
        if datetime.fromisoformat(e["start"]).date() in mentioned:
            score = max(score, 0.5)
        if len(near) == 1 and e in near:
            score = max(score, 0.5)
        if score > best_score:
            best, best_score = e, score
    return best if best_score >= 0.5 else None


def apply(ev, kind, post, raw, t, tz, ref):
    """Record the update on the event (and change status/location/start when we can tell how)."""
    upd = {"kind": kind, "at": post.taken_at.isoformat(), "url": post.url}
    if kind == "cancelled":
        ev["status"] = "cancelled"
    elif kind == "location":
        new = details.find_location(raw)
        if new:
            upd["old"] = (ev.get("location") or {}).get("text")
            upd["new"] = new["text"]
            ev["location"] = new
    elif kind == "rescheduled" and not ev.get("recurrence"):
        old = datetime.fromisoformat(ev["start"])
        hits = [h for h in dates.find_dates(t, ref) if h.kind == "event"]
        st, _ = dates.find_times(t)
        new_date = next((h.start for h in hits if h.start != old.date()), hits[0].start if hits else old.date())
        if hits or st:
            new = datetime.combine(new_date, st or (old.time() if not ev["date_only"] else datetime.min.time()), tzinfo=tz)
            if new != old:
                upd["old"], upd["new"] = ev["start"], new.isoformat()
                ev["start"] = new.isoformat()
                ev["end"] = (new + timedelta(minutes=ev["duration_min"])).isoformat() if ev.get("duration_min") else None
                ev["date_only"] = ev["date_only"] and st is None
    ev["updates"].append(upd)
    return upd
