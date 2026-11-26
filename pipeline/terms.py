"""Academic term dates (Fall / Winter / Summer). Used only to guess the end date of recurring
events whose post gives no end date. Scraped from the uOttawa page at most twice a year;
config.yaml 'terms.override' always wins."""
import json
import re
from datetime import date, datetime
from pathlib import Path


def default_terms(today):
    y = today.year if today.month >= 8 else today.year - 1
    return {"fall": {"start": f"{y}-09-01", "end": f"{y}-12-31"},
            "winter": {"start": f"{y+1}-01-01", "end": f"{y+1}-04-30"},
            "summer": {"start": f"{y+1}-05-01", "end": f"{y+1}-08-31"}}


def _scrape(url, today):
    """EXPERIMENTAL best-effort: look for 'classes begin/end' lines and sort them into terms by month."""
    import requests
    from bs4 import BeautifulSoup
    from .dates import find_dates, norm
    html = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"}).text
    out = {}
    for line in BeautifulSoup(html, "html.parser").get_text("\n").splitlines():
        t = norm(line)
        is_end = re.search(r"classes end|last day of classes|end of classes|fin des cours", t)
        is_start = re.search(r"classes begin|first day of classes|start of classes|debut des cours", t)
        if not (is_end or is_start):
            continue
        hits = find_dates(t, today)
        if not hits:
            continue
        d, slot = hits[0].start, None
        if is_end:
            slot = {12: ("fall", "end"), 4: ("winter", "end"), 3: ("winter", "end"), 8: ("summer", "end"), 7: ("summer", "end")}.get(d.month)
        else:
            slot = {9: ("fall", "start"), 8: ("fall", "start"), 1: ("winter", "start"), 5: ("summer", "start"), 6: ("summer", "start")}.get(d.month)
        if slot:
            out.setdefault(slot[0], {}).setdefault(slot[1], d.isoformat())
    return out


def load(cfg, today, cache_path, allow_network=True):
    terms = default_terms(today)
    cache_path = Path(cache_path)
    cached = json.loads(cache_path.read_text()) if cache_path.exists() else None
    fresh = cached and (today - date.fromisoformat(cached["fetched_at"])).days < 180
    if not fresh and allow_network:
        try:
            cached = {"fetched_at": today.isoformat(), "terms": _scrape(cfg["terms"]["url"], today)}
            cache_path.write_text(json.dumps(cached, indent=1))
        except Exception as e:
            print("  terms: could not read the uOttawa page, using defaults/override:", e)
    for name, vals in ((cached or {}).get("terms") or {}).items():
        terms[name].update(vals)
    for name, vals in (cfg["terms"].get("override") or {}).items():
        terms[name].update({k: str(v) for k, v in vals.items()})
    return terms


def _shift(d, k):
    try:
        return d.replace(year=d.year + k)
    except ValueError:
        return d.replace(year=d.year + k, day=28)


def assumed_end(terms, d):
    """End of the school year (Winter end) for Fall/Winter events, end of Summer for Summer events."""
    p = date.fromisoformat
    for k in range(-3, 4):
        a, b = _shift(p(terms["fall"]["start"]), k), _shift(p(terms["fall"]["start"]), k + 1)
        if a <= d < b:
            if d >= _shift(p(terms["summer"]["start"]), k):
                return _shift(p(terms["summer"]["end"]), k)
            return _shift(p(terms["winter"]["end"]), k)
    return _shift(p(terms["winter"]["end"]), 0)
