"""
Date + time extraction for English AND French text.
Everything here works on *normalised* text: lowercase, accents removed (see norm()).
Find dates with find_dates(), times with find_times().
"""
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, time, timedelta


def norm(s):
    """lowercase + strip accents so 'Août' == 'aout' and 'à' == 'a'."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return (s.lower().replace("\u00a0", " ").replace("’", "'")
             .replace("–", "-").replace("—", "-"))


MONTHS = {}
for _n, _names in enumerate([
        "january jan janvier janv", "february feb febr fevrier fevr fev", "march mar mars",
        "april apr avril avr", "may mai", "june jun juin", "july jul juillet juil",
        "august aug aout", "september sep sept septembre", "october oct octobre",
        "november nov novembre", "december dec decembre"], 1):
    for _w in _names.split():
        MONTHS[_w] = _n

WEEKDAYS = {"monday": 0, "lundi": 0, "tuesday": 1, "mardi": 1, "wednesday": 2, "mercredi": 2,
            "thursday": 3, "jeudi": 3, "friday": 4, "vendredi": 4, "saturday": 5, "samedi": 5,
            "sunday": 6, "dimanche": 6}

MON = "|".join(sorted(MONTHS, key=len, reverse=True))
WD = "|".join(sorted(WEEKDAYS, key=len, reverse=True))
ORD = r"(?:st|nd|rd|th|er)?"
RNG = r"\s*(?:-|\bto\b|\bthrough\b|\bthru\b|\bau\b|\ba\b)\s*"
NOT_TIME = r"(?!\s*(?:h\b|:|[ap]\.?\s?m\b))"   # "Nov 28 - 6pm" must not be read as a day range
YEAR = r"(?:\s*,?\s*(20\d\d))?"

P_MD_RANGE = re.compile(rf"\b({MON})\.?\s+(\d{{1,2}}){ORD}{RNG}(?:({MON})\.?\s+)?(\d{{1,2}}){ORD}\b{NOT_TIME}{YEAR}")
P_DM_RANGE = re.compile(rf"\b(\d{{1,2}}){ORD}(?:\s+(?:de\s+)?({MON})\b\.?)?{RNG}(\d{{1,2}}){ORD}\s+(?:de\s+|d')?({MON})\b\.?{YEAR}")
P_MD = re.compile(rf"\b({MON})\.?\s+(\d{{1,2}}){ORD}\b{YEAR}")
P_DM = re.compile(rf"(?<![\d:])\b(\d{{1,2}}){ORD}\s+(?:de\s+|d')?({MON})\b\.?{YEAR}")
P_ISO = re.compile(r"\b(20\d\d)-(\d{2})-(\d{2})\b")
P_NUM = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?(?![\d/])")
P_WD = re.compile(rf"(?:\b(this|next|ce|cette)\s+)?\b({WD})s?\b(?:\s+(prochain|next))?")

DEADLINE_RE = re.compile(
    r"(?:deadline|date limite|limite d'inscription)\W*(?:is\s*|:)?\W*$"
    r"|(?:register|registration|sign[- ]?ups?|apply|applications?|rsvp|inscri\w+|submit\w*|reserv\w+)\b.*"
    r"\b(?:by|before|until|avant|jusqu'?(?:au|a)|closes?|ends?|ferme\w*)\s*(?:on\s+|le\s+)?$"
    r"|clos(?:es|ing)\s*(?:on\s+)?$")
UNTIL_RE = re.compile(r"(?:until|till|through|thru|jusqu'?(?:au|a)|ends?|se termine)\s*(?:le\s+)?$")


@dataclass
class DateHit:
    start: date
    end: date = None      # set for ranges like "Nov 28-30"
    pos: int = 0
    kind: str = "event"   # "event" | "deadline" | "until"


def _mk(mon, day, year, ref):
    """Build a date; if no year is given pick the one that makes sense relative to the post date."""
    try:
        if year:
            return date(int(year), mon, int(day))
        d = date(ref.year, mon, int(day))
        if d < ref - timedelta(days=60):
            d = date(ref.year + 1, mon, int(day))
        return d
    except ValueError:
        return None


def _classify(t, pos):
    seg = re.split(r"[.\n!?;|]", t[max(0, pos - 60):pos])[-1]   # only the current sentence
    if DEADLINE_RE.search(seg):
        return "deadline"
    if UNTIL_RE.search(seg):
        return "until"
    return "event"


def next_weekday(ref, wd, nxt=False):
    d = ref + timedelta(days=(wd - ref.weekday()) % 7)
    if nxt:
        if d == ref or d.isocalendar()[:2] == ref.isocalendar()[:2]:
            d += timedelta(days=7)
    return d


def find_dates(t, ref, dmy=False):
    """Return a list of DateHit found in normalised text t. `ref` = date the post was published."""
    hits, taken = [], []

    def add(m, s, e=None):
        if s is None or any(m.start() < b and a < m.end() for a, b in taken):
            return
        if e is not None and e < s:
            e = e.replace(year=e.year + 1)
        taken.append((m.start(), m.end()))
        hits.append(DateHit(s, e, m.start(), _classify(t, m.start())))

    for m in P_MD_RANGE.finditer(t):
        m1, d1, m2, d2, y = m.groups()
        add(m, _mk(MONTHS[m1], d1, y, ref), _mk(MONTHS[m2 or m1], d2, y, ref))
    for m in P_DM_RANGE.finditer(t):
        d1, m1, d2, m2, y = m.groups()
        add(m, _mk(MONTHS[m1 or m2], d1, y, ref), _mk(MONTHS[m2], d2, y, ref))
    for m in P_ISO.finditer(t):
        add(m, _mk(int(m.group(2)), m.group(3), m.group(1), ref))
    for m in P_MD.finditer(t):
        add(m, _mk(MONTHS[m.group(1)], m.group(2), m.group(3), ref))
    for m in P_DM.finditer(t):
        add(m, _mk(MONTHS[m.group(2)], m.group(1), m.group(3), ref))
    for m in P_NUM.finditer(t):
        a, b, y = int(m.group(1)), int(m.group(2)), m.group(3)
        if y and len(y) == 2:
            y = "20" + y
        mon, day = (b, a) if (dmy or a > 12) and b <= 12 else (a, b)
        if 1 <= mon <= 12:
            add(m, _mk(mon, day, y, ref))

    if not [h for h in hits if h.kind == "event"]:   # relative dates ("tomorrow") when no explicit EVENT date
        m = re.search(r"\b(?:the day after tomorrow|apres[- ]demain)\b", t)
        if m:
            hits.append(DateHit(ref + timedelta(days=2), None, m.start()))
        elif (m := re.search(r"\b(?:today|tonight|tonite|2night|this evening|aujourd'?hui|ce soir)\b", t)):
            hits.append(DateHit(ref, None, m.start()))
        elif (m := re.search(r"\b(?:tomorrow|tmrw|tmr|tmrw|2morrow|2moro|demain)\b", t)):
            hits.append(DateHit(ref + timedelta(days=1), None, m.start()))
        elif (m := re.search(r"\b(this weekend|ce week-?end|cette fin de semaine)\b", t)):
            hits.append(DateHit(next_weekday(ref, 5), None, m.start()))
        elif (m := P_WD.search(t)):
            nxt = m.group(1) == "next" or m.group(3) in ("prochain", "next")
            hits.append(DateHit(next_weekday(ref, WEEKDAYS[m.group(2)], nxt), None, m.start()))
    return sorted(hits, key=lambda h: h.pos)


# ---------------------------------------------------------------- times
_T24 = r"(\d{1,2})(?:(?::|h)(\d{2})|\s?h(?![a-z0-9]))"      # 18:30  18h30  18h
_SEP = r"\s*(?:-|\bto\b|\buntil\b|\btill\b|\bau\b|\ba\b|\bjusqu'?a\b)\s*"
_AP = r"([ap])\.?\s?m\b\.?"
R_AMPM_RANGE = re.compile(rf"(?<![\d:])(\d{{1,2}})(?::(\d{{2}}))?\s*(?:{_AP})?{_SEP}(\d{{1,2}})(?::(\d{{2}}))?\s*{_AP}")
R_24_RANGE = re.compile(rf"(?<![\d:]){_T24}{_SEP}{_T24}")
R_AMPM = re.compile(rf"(?<![\d:])(\d{{1,2}})(?::(\d{{2}}))?\s*{_AP}")
R_24 = re.compile(rf"(?<![\d:]){_T24}")
R_WORD = re.compile(r"\b(noon|midi|midnight|minuit)\b")


def _t(h, m, ap=None, guess_pm=False):
    h, m = int(h), int(m or 0)
    if ap:
        if not 1 <= h <= 12:
            return None
        h = h % 12 + (12 if ap == "p" else 0)
    elif guess_pm and 1 <= h <= 7:      # "6:30" with no am/pm -> evening
        h += 12
    return time(h, m) if h < 24 and m < 60 else None


def find_times(t):
    """Return (start_time, end_time) of the first time/range found, or (None, None)."""
    cands = []   # (position, -length, start, end)
    for m in R_AMPM_RANGE.finditer(t):
        h1, m1, a1, h2, m2, a2 = m.groups()
        if a1 is None:
            a1 = "a" if (int(h1) % 12 > int(h2) % 12 and a2 == "p") else a2
        s, e = _t(h1, m1, a1), _t(h2, m2, a2)
        if s and e:
            cands.append((m.start(), -len(m.group()), s, e))
    for m in R_24_RANGE.finditer(t):
        h1, m1, h2, m2 = m.groups()
        s, e = _t(h1, m1), _t(h2, m2)
        if s and e:
            cands.append((m.start(), -len(m.group()), s, e))
    for m in R_AMPM.finditer(t):
        s = _t(m.group(1), m.group(2), m.group(3))
        if s:
            cands.append((m.start(), -len(m.group()), s, None))
    for m in R_24.finditer(t):
        h, mi = m.groups()
        s = _t(h, mi, None, guess_pm=bool(mi) and not h.startswith("0"))
        if s:
            cands.append((m.start(), -len(m.group()), s, None))
    for m in R_WORD.finditer(t):
        cands.append((m.start(), -len(m.group()), time(12) if m.group(1) in ("noon", "midi") else time(0), None))
    if not cands:
        return None, None
    c = min(cands, key=lambda x: (x[0], x[1]))
    return c[2], c[3]
