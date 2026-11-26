"""Turn ONE post (caption + OCR text merged) into an event dict, or None if no date is found."""
import re
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from . import dates, details
from . import terms as terms_mod
from .translate import translate


def build_event(post, ocr_text, account, terms, cfg):
    tz = ZoneInfo(cfg["timezone"])
    caption = post.caption or ""
    raw = (caption + "\n" + (ocr_text or "")).strip()   # merge caption + image text
    t = dates.norm(raw)
    lang = details.language_info(t)
    ref = post.taken_at.astimezone(tz).date()
    hits = dates.find_dates(t, ref, dmy=(lang["text_lang"] == "fr"))
    ev_hits = [h for h in hits if h.kind == "event"]
    dl_hits = [h for h in hits if h.kind == "deadline"]
    until_hits = [h for h in hits if h.kind == "until"]
    main = ev_hits[0] if ev_hits else (dl_hits[0] if dl_hits else None)
    if main is None:
        return None                                  # no clear date anywhere -> skip the post

    start_t, end_t = dates.find_times(t)
    start_date, end_date = main.start, main.end
    combine = lambda d, tm: datetime.combine(d, tm, tzinfo=tz)

    # ---- recurrence (only if the post says so)
    recurrence = None
    rec = details.find_recurrence(t)
    if rec:
        wd = rec["weekday"] if rec["weekday"] is not None else start_date.weekday()
        start_date = start_date + timedelta(days=(wd - start_date.weekday()) % 7)
        end_date = None
        until = until_hits[0].start if until_hits else terms_mod.assumed_end(terms, start_date)
        occ, d = [], start_date
        while d <= until and len(occ) < 80:
            occ.append(combine(d, start_t or time(0)).isoformat())
            d += timedelta(days=rec["step"])
        recurrence = {"freq": "weekly" if rec["step"] == 7 else "biweekly", "until": until.isoformat(),
                      "until_assumed": not until_hits, "occurrences": occ or [combine(start_date, start_t or time(0)).isoformat()]}

    start = combine(start_date, start_t or time(0))
    end = None
    if end_t:
        end = combine(end_date or start_date, end_t)
        if end <= start:
            end += timedelta(days=1)
    elif end_date:
        end = combine(end_date, time(23, 59))
    duration = int((end - start).total_seconds() // 60) if (end and start_t) else None

    # ---- dependency (sign-up deadline or numbered series)
    dep = {}
    if dl_hits:
        dep["deadline"] = dl_hits[0].start.isoformat()
    ser = details.find_series(t)
    title = details.guess_title(caption, ocr_text)
    if ser:
        key = re.sub(r"\s+", " ", re.sub(r"[\d#]+|\b(?:workshop|session|part|week|atelier|seance|partie|of|de)\b", "", dates.norm(title))).strip()
        dep.update({"series_key": f"{post.handle}:{key}", "index": ser["index"], "total": ser["total"]})

    # ---- title / description in both languages
    desc = details.clean_description(caption, ocr_text)
    title_en = title_fr = title
    desc_en = desc_fr = desc
    translated_from = None
    split = details.split_bilingual_title(title)
    if split:
        title_en, title_fr = split
    elif lang["note"] in ("only_en", "only_fr"):
        src = "en" if lang["note"] == "only_en" else "fr"
        dst = "fr" if src == "en" else "en"
        tt, dd = translate(title, src, dst), translate(desc, src, dst)
        if tt or dd:
            translated_from = src
            if src == "en":
                title_fr, desc_fr = tt or title, dd or desc
            else:
                title_en, desc_en = tt or title, dd or desc

    return {
        "id": f"{post.platform}:{post.post_id}",
        "platform": post.platform, "post_id": post.post_id, "post_url": post.url,
        "posted_at": post.taken_at.isoformat(),
        "club": {"handle": account["handle"], "name": account.get("name") or "", "acronym": account.get("acronym") or "", "avatar": None},
        "category": account.get("category", "other"), "tags": [account.get("category", "other")],
        "title": {"en": title_en, "fr": title_fr},
        "description": {"en": desc_en, "fr": desc_fr},
        "start": start.isoformat(), "end": end.isoformat() if end else None,
        "end_date": end_date.isoformat() if end_date else None,
        "date_only": start_t is None, "duration_min": duration,
        "location": details.find_location(raw),
        "rsvp_required": details.find_rsvp(t),
        "cost": details.find_cost(t),
        "languages": lang["langs"], "language_note": lang["note"], "translated_from": translated_from,
        "recurrence": recurrence, "dependency": dep or None,
        "updates": [], "status": "active",
    }
