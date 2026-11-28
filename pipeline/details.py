"""Small helpers that pull everything *except* the date/time out of the text:
title, location, RSVP, cost, language, recurrence, series."""
import re
from .dates import WD, WEEKDAYS

EMOJI = re.compile(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200d]")


def clean_line(s):
    s = EMOJI.sub(" ", s)
    s = re.sub(r"https?://\S+|[#@]\S+", " ", s)
    return re.sub(r"\s+", " ", s).strip(" -–—|:•*·_.")


# ------------------------------------------------------------------ title
SKIP_LINE = re.compile(r"^(?:when|where|date|time|quand|lieu|location|ou|où|heure)\b", re.I)


NOTE_LANG = re.compile(r"\b(english|french|francais|anglais|version)\b")
NOTE_WORDS = re.compile(r"follow|below|suit|dessous|suivre|\bbas\b")


def _is_language_note(c):
    """'(English follows)', 'Version française ci-dessous'... are not titles."""
    from .dates import norm
    n = norm(c)
    return len(n) < 60 and bool(NOTE_LANG.search(n) and NOTE_WORDS.search(n))


def _cut_at_date(c):
    """'Cooking Workshop 1 of 2: November 23 at 6pm' -> 'Cooking Workshop 1 of 2' (keep only the name part)."""
    from . import dates
    n = dates.norm(c)
    if len(n) != len(c):
        return c
    spots = [m.start() for rx in (dates.P_MD, dates.P_DM, dates.R_AMPM, dates.R_24)
             for m in [rx.search(n)] if m]
    spots += [m.start() for m in [re.search(r"\b(?:tonight|tomorrow|ce soir|demain|today)\b", n)] if m]
    pos = min(spots) if spots else -1
    if pos >= 8:
        cut = re.sub(r"(?:\s+(?:on|at|le|à|the))*[\s:,@(\-]*$", "", c[:pos])
        if len(cut) >= 6:
            return cut
    return c


def guess_title(caption, ocr):
    for src in (caption, ocr):                       # caption first, poster text second
        for line in (src or "").splitlines():
            c = clean_line(line)
            if len(re.findall(r"[A-Za-zÀ-ÿ]", c)) < 4 or SKIP_LINE.match(c) or _is_language_note(c):
                continue
            if len(c) > 90:
                parts = re.split(r"(?<=[.!?])\s", c)
                c, i = parts[0], 1
                while len(c) < 25 and i < len(parts):      # "C'EST DEMAIN !" alone is a bad title
                    c, i = c + " " + parts[i], i + 1
                if len(c) > 90:
                    c = c[:90].rsplit(" ", 1)[0] + "…"
            return _cut_at_date(c)
    return "Event"


INFO_PIN = re.compile(r"^\s*[📍📌🏢]")
INFO_TIME = re.compile(r"^\s*[📅🗓🕒🕐-🕧⏰⏱🕰ℹ]")


def strip_info_lines(text, has_location, has_time):
    """Drop '📍 place' and '🕒 time' lines when those facts are already shown as their own fields."""
    out = []
    for line in (text or "").splitlines():
        if (has_location and INFO_PIN.match(line)) or (has_time and INFO_TIME.match(line)):
            continue
        out.append(line)
    return "\n".join(out)


def clean_description(caption, ocr):
    text = caption if (caption or "").strip() else (ocr or "")
    text = re.sub(r"(?:^|\s)#\w+", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:600] + ("…" if len(text) > 600 else "")


# --------------------------------------------------------------- language
EN_WORDS = set("the and of to in at for with is are will join our we you your this that from be come free all welcome us".split())
FR_WORDS = set("le la les des du un une et est sont pour avec nous vous votre notre ce cette dans sur au aux venez joignez rejoignez gratuit soir rencontre inscription bienvenue de en ou".split())
EN_ONLY = re.compile(r"english only|only in english|in english only|in english exclusively|uniquement en anglais|seulement en anglais|en anglais seulement|en anglais uniquement|anglais seulement")
FR_ONLY = re.compile(r"french only|only in french|in french only|in french exclusively|uniquement en francais|seulement en francais|en francais seulement|en francais uniquement|francais seulement")


def lang_counts(t):
    words = re.findall(r"[a-z]+", t)
    return sum(w in EN_WORDS for w in words), sum(w in FR_WORDS for w in words)


def language_info(t):
    """t = normalised text. Returns langs offered, a disclaimer key and the main text language."""
    en, fr = lang_counts(t)
    main = "en" if en >= fr else "fr"
    en_only, fr_only = EN_ONLY.search(t), FR_ONLY.search(t)
    bilingual = ("bilingual" in t or "bilingue" in t or (en >= 4 and fr >= 4 and min(en, fr) / (en + fr) >= 0.25))
    if bilingual or (en_only and fr_only):
        return {"langs": ["en", "fr"], "note": None, "text_lang": "both"}
    if en_only:
        return {"langs": ["en"], "note": "only_en", "text_lang": "en"}
    if fr_only:
        return {"langs": ["fr"], "note": "only_fr", "text_lang": "fr"}
    if en + fr < 3:
        return {"langs": [], "note": None, "text_lang": main}
    return {"langs": [main], "note": "maybe_" + main, "text_lang": main}


def split_bilingual(caption):
    """Posts that contain both languages: sort the caption line by line into an English text and a
    French text (lines with no clear language, like dates and places, go into both)."""
    from .dates import norm
    en_lines, fr_lines, titles = [], [], {}
    for line in (caption or "").splitlines():
        c = clean_line(line)
        if not c or _is_language_note(c):
            continue
        en, fr = lang_counts(norm(c))
        side = "en" if en > fr else "fr" if fr > en else None
        if side != "fr":
            en_lines.append(line)
        if side != "en":
            fr_lines.append(line)
        if side and side not in titles and len(re.findall(r"[A-Za-zÀ-ÿ]", c)) >= 4 and not SKIP_LINE.match(c):
            titles[side] = _cut_at_date(c) if len(c) <= 90 else guess_title(line, "")
    en_text, fr_text = "\n".join(en_lines).strip(), "\n".join(fr_lines).strip()
    if len(en_text) < 15 or len(fr_text) < 15:
        return None
    return {"en": en_text, "fr": fr_text, "title_en": titles.get("en"), "title_fr": titles.get("fr")}


def split_bilingual_title(title):
    """'Resume Workshop | Atelier de CV' -> ('Resume Workshop', 'Atelier de CV')"""
    from .dates import norm
    parts = [p.strip() for p in re.split(r"\s[|/]\s", title) if p.strip()]
    if len(parts) == 2:
        a, b = (lang_counts(norm(p)) for p in parts)
        if a[0] > a[1] and b[1] > b[0]:
            return parts[0], parts[1]
        if a[1] > a[0] and b[0] > b[1]:
            return parts[1], parts[0]
    return None


# --------------------------------------------------------------- location
STOP_AT = re.compile(r"[\U0001F000-\U0001FAFF\u2600-\u27BF]|\s\|\s|\n")
LOC_LABEL = re.compile(r"^\W*(?:location|where|venue|lieu|endroit|salle|local|ou|où|room)\s*[:\-]\s*(.+)$", re.I)
VENUE = re.compile(r"\b(?:University Centre|UCU|Tabaret(?: Hall)?|Lamoureux(?: Hall)?|Minto|Colonel By|Learning Crossroads|"
                   r"Morisset|Fauteux|Desmarais|Roger Guindon|Montpetit|Vanier|Marion|STEM Complex|Hamelin|Brunsfield|"
                   r"Jock Turcot)\b(?:\s+(?:room\s+|salle\s+)?[A-Z]?\d{2,4}[A-Z]?)?", re.I)
ROOM_LABEL = re.compile(r"\b(?:room|salle|local)\s+[A-Z]{0,4}\s?\d{2,4}[A-Z]?\b", re.I)
ROOM_CODE = re.compile(r"(?:\bat|\bin|\bà|\bdans|@)\s+([A-Z]{2,5}\s?[A-Z]?\d{3,4}[A-Z]?)\b")
ONLINE = re.compile(r"\b(?:zoom|google meet|teams|online|en ligne|virtual|virtuel|discord)\b", re.I)


def find_location(raw):
    """Return {'text':..., 'online':bool} or None. Tries pin emoji, 'Location:' labels, known venues, room codes."""
    for line in raw.splitlines():
        seg = None
        if "📍" in line:
            seg = STOP_AT.split(line.split("📍", 1)[1].lstrip("️ :"))[0]
        else:
            m = LOC_LABEL.match(line)
            if m:
                seg = STOP_AT.split(m.group(1))[0]
        seg = clean_line(seg or "")
        if len(seg) >= 2:
            return {"text": seg[:80], "online": bool(ONLINE.fullmatch(seg))}
    for rx, grp in ((VENUE, 0), (ROOM_LABEL, 0), (ROOM_CODE, 1)):
        m = rx.search(raw)
        if m:
            return {"text": m.group(grp).strip(), "online": False}
    if ONLINE.search(raw):
        return {"text": "Online", "online": True}
    return None


# ------------------------------------------------------------- rsvp / cost
NO_RSVP = re.compile(r"no (?:rsvp|registration|sign[- ]?up)|drop[- ]?in|walk[- ]?ins?|sans inscription|aucune inscription|"
                     r"pas (?:besoin|d')\s*(?:de |d')?(?:s'inscrire|inscription|rsvp)|no need to (?:register|rsvp)|rsvp not required")
NEED_RSVP = re.compile(r"\brsvp\b|register|registration|sign[- ]?ups?\b|inscri\w+|reserv\w+")


def find_rsvp(t):
    """Drop-in unless the post asks people to register."""
    return bool(NEED_RSVP.search(t)) and not NO_RSVP.search(t)


FREE = re.compile(r"free (?:admission|entry|event|of charge|to attend)|no cost|no charge|entree libre|sans frais|gratuit|"
                  r"\bfree\b(?! (?:food|pizza|swag|merch|snacks?|drinks?|coffee|tea|lunch|breakfast|dinner|stuff|t-?shirts?))")
PRICE = re.compile(r"\$\s?(\d+(?:[.,]\d{1,2})?)|(\d+(?:[.,]\d{1,2})?)\s?\$")


def find_cost(t):
    free, price = FREE.search(t), PRICE.search(t)
    amount = None
    if price:
        amount = "$" + (price.group(1) or price.group(2)).replace(",", ".")
    if free and price:
        return {"type": "mixed", "amount": amount}
    if price:
        return {"type": "paid", "amount": amount}
    if free:
        return {"type": "free", "amount": None}
    return {"type": "unknown", "amount": None}


# -------------------------------------------------- recurrence / series
EVERY = re.compile(rf"\b(?:every|each|chaque|tous\s+les|toutes\s+les)\s+(?:other\s+)?(?:({WD})s?\b|week\b|semaine\b)")
WEEKLY = re.compile(r"\b(?:weekly|hebdomadaire|hebdo)\b")
BIWEEKLY = re.compile(r"\bbi-?weekly\b|\bevery other\b|\bevery two weeks\b|toutes les deux semaines|aux deux semaines")


def find_recurrence(t):
    """Only 'recurring' if the post says so. Returns {'step': 7|14, 'weekday': int|None} or None."""
    m = EVERY.search(t)
    if not (m or WEEKLY.search(t) or BIWEEKLY.search(t)):
        return None
    step = 14 if BIWEEKLY.search(t) else 7
    return {"step": step, "weekday": WEEKDAYS[m.group(1)] if m and m.group(1) else None}


SERIES = re.compile(r"\b(?:workshop|session|part|week|atelier|seance|partie|semaine|module|class)\s*#?(\d{1,2})\s*(?:of|/|de|sur)\s*(\d{1,2})\b")


def find_series(t):
    m = SERIES.search(t)
    return {"index": int(m.group(1)), "total": int(m.group(2))} if m else None
