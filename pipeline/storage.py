"""Reading/writing the JSON files + the keep/delete rules for events."""
import json
from datetime import date, datetime, time, timedelta
from pathlib import Path


def read_json(path, default):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def write_json(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def save_avatar(url, handle, folder):
    """Download + shrink the profile picture so the site never hotlinks Instagram."""
    try:
        import requests
        from io import BytesIO
        from PIL import Image
        img = Image.open(BytesIO(requests.get(url, timeout=30).content)).convert("RGB")
        img.thumbnail((112, 112))
        Path(folder).mkdir(parents=True, exist_ok=True)
        img.save(Path(folder) / f"{handle}.jpg", quality=85)
    except Exception as e:
        print(f"  avatar for {handle} failed: {e}")


def save_image(url, path, max_width=720):
    """Download a post picture, shrink it (small files = fast site) and save it as a JPEG."""
    try:
        import requests
        from io import BytesIO
        from PIL import Image
        img = Image.open(BytesIO(requests.get(url, timeout=30).content)).convert("RGB")
        if img.width > max_width:
            img = img.resize((max_width, round(img.height * max_width / img.width)))
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        img.save(path, "JPEG", quality=72, optimize=True)
        return True
    except Exception as e:
        print(f"  poster download failed: {str(e)[:100]}")
        return False


def _end_of_day(d, tz):
    return datetime.combine(d, time(23, 59, 59), tzinfo=tz)


def _keep(ev, now, cfg, tz):
    rec = ev.get("recurrence")
    if rec:                                                  # recurring: until its termination date
        return date.fromisoformat(rec["until"]) >= now.date()
    dep = ev.get("dependency") or {}
    if dep.get("deadline"):                                  # sign-up deadline: until it passes
        return _end_of_day(date.fromisoformat(dep["deadline"]), tz) >= now
    start = datetime.fromisoformat(ev["start"])
    if ev["date_only"]:
        end = _end_of_day((date.fromisoformat(ev["end_date"]) if ev.get("end_date") else start.date()), tz)
    else:
        end = datetime.fromisoformat(ev["end"]) if ev.get("end") else start + timedelta(hours=2)
    return end >= now - timedelta(days=cfg["missed_days"])


def prune(events, now, cfg, tz):
    """Apply the deletion rules. Returns a new dict."""
    keep = {i: e for i, e in events.items() if _keep(e, now, cfg, tz)}
    # numbered series ("Workshop 2 of 4"): once session 1 has started, later sessions are no longer joinable
    started = {e["dependency"]["series_key"] for e in keep.values()
               if (e.get("dependency") or {}).get("index") == 1 and datetime.fromisoformat(e["start"]) <= now}
    return {i: e for i, e in keep.items()
            if not ((e.get("dependency") or {}).get("index", 1) > 1 and e["dependency"]["series_key"] in started)}


def public_payload(events, cfg, now):
    return {"generated_at": now.isoformat(), "timezone": cfg["timezone"], "categories": cfg["categories"],
            "events": sorted(events.values(), key=lambda e: e["start"])}
