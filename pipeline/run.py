"""
THE MAIN SCRIPT.   python -m pipeline.run            (real scrape)
                   python -m pipeline.run --demo     (fake posts -> site/data/events.demo.json)

Flow:  read config -> for each account: fetch posts -> OCR -> extract event -> update/merge
       -> delete expired events -> write site/data/events.json
"""
import hashlib
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from . import dates, details, extract, ocr, storage, updates
from . import terms as terms_mod
from .sources import get_source

ROOT = Path(__file__).resolve().parent.parent
EVENTS_FILE = ROOT / "site" / "data" / "events.json"


def process_post(post, account, ctx):
    """Handle one post. Returns 'new', 'updated' or None."""
    cfg, tz = ctx["cfg"], ctx["tz"]
    key = f"{post.platform}:{post.post_id}"
    rec = ctx["posts"].get(key)
    h = hashlib.sha1((post.caption or "").encode("utf-8")).hexdigest()
    if rec and rec["hash"] == h:
        return None                                   # unchanged since last run: skip (no OCR needed)
    ocr_text = rec["ocr"] if rec else ocr.ocr_post(post)
    raw = (post.caption or "") + "\n" + ocr_text
    t = dates.norm(raw)
    ref = post.taken_at.astimezone(tz).date()
    entry = {"hash": h, "ocr": ocr_text, "event_id": None, "seen": ctx["now"].date().isoformat()}
    ctx["posts"][key] = entry
    if rec and rec.get("update"):                     # an update post that was edited: don't apply twice
        entry.update(update=True, event_id=rec["event_id"])
        return None

    kind = updates.find_kind(t)                       # cancelled / rescheduled / room change?
    if kind:
        target = updates.match_event(ctx["events"], post, t, ref, ctx["now"])
        if target:
            updates.apply(target, kind, post, raw, t, tz, ref)
            entry.update(update=True, event_id=target["id"])
            return "updated"

    ev = extract.build_event(post, ocr_text, account, ctx["terms"], cfg)
    if ev is None:
        return None                                   # no date -> not an event
    old = ctx["events"].get(ev["id"])
    if old:                                           # caption was edited: keep history
        ev["updates"], ev["status"] = old["updates"], old["status"]
    ctx["events"][ev["id"]] = ev
    entry["event_id"] = ev["id"]
    return "new"


def main(demo=False):
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    tz = ZoneInfo(cfg["timezone"])
    now = datetime.now(tz)
    accounts = {(p, a["handle"]): a for p, lst in cfg["accounts"].items() for a in (lst or [])}
    avatars = ROOT / "site" / "data" / "avatars"

    ctx = {"cfg": cfg, "tz": tz, "now": now,
           "terms": terms_mod.load(cfg, now.date(), ROOT / "data" / "terms.json", allow_network=not demo)}
    if demo:
        from .demo_posts import make
        ctx["posts"], ctx["events"], state = {}, {}, {"accounts": {}}
        batches = [(("instagram", p.handle), p) for p in sorted(make(now), key=lambda p: p.taken_at)]
        for (plat, handle), post in batches:
            acct = accounts.get((plat, handle), {"handle": handle, "category": "other"})
            process_post(post, acct, ctx)
        status = {}
    else:
        state = storage.read_json(ROOT / "data" / "state.json", {"accounts": {}})
        ctx["posts"] = storage.read_json(ROOT / "data" / "posts.json", {})
        ctx["events"] = {e["id"]: e for e in storage.read_json(EVENTS_FILE, {}).get("events", [])}
        status = {}
        for (plat, handle), acct in accounts.items():
            skey = f"{plat}:{handle}"
            first = skey not in state["accounts"]
            limit = cfg["posts_first_run"] if first else cfg["posts_per_run"]
            print(f"[{skey}] fetching {limit} posts{' (first scrape)' if first else ''}")
            try:
                info, posts = get_source(plat).fetch(acct, limit)
            except Exception as e:                    # one broken account must never stop the others
                status[skey] = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:150]}"}
                print("  FAILED:", status[skey]["error"])
                time.sleep(random.uniform(3, 6))
                continue
            if info.get("avatar_url"):
                storage.save_avatar(info["avatar_url"], handle, avatars)
            results = [process_post(p, acct, ctx) for p in sorted(posts, key=lambda p: p.taken_at)]
            state["accounts"][skey] = {"first_scraped": state["accounts"].get(skey, {}).get("first_scraped", now.isoformat()), "last_ok": now.isoformat()}
            status[skey] = {"ok": True, "posts": len(posts), "new": results.count("new"), "updates": results.count("updated")}
            print("  ok:", status[skey])
            time.sleep(random.uniform(4, 8))

    # club avatars + prune + write
    for ev in ctx["events"].values():
        f = avatars / f"{ev['club']['handle']}.jpg"
        ev["club"]["avatar"] = f"data/avatars/{ev['club']['handle']}.jpg" if f.exists() else None
        acct = accounts.get((ev["platform"], ev["club"]["handle"]))
        if acct:                                      # pick up edits made in config.yaml
            ev["club"].update(name=acct.get("name") or "", acronym=acct.get("acronym") or "")
            ev["category"] = acct.get("category", "other")
    events = storage.prune(ctx["events"], now, cfg, tz)
    payload = storage.public_payload(events, cfg, now)
    if demo:
        storage.write_json(ROOT / "site" / "data" / "events.demo.json", payload)
        print(f"demo: wrote {len(events)} events to site/data/events.demo.json")
    else:
        storage.write_json(EVENTS_FILE, payload)
        storage.write_json(ROOT / "site" / "data" / "status.json", {"last_run": now.isoformat(), "accounts": status})
        storage.write_json(ROOT / "data" / "state.json", state)
        keep_after = now.date().toordinal() - 120
        ctx["posts"] = {k: v for k, v in ctx["posts"].items() if datetime.fromisoformat(v["seen"]).toordinal() >= keep_after}
        storage.write_json(ROOT / "data" / "posts.json", ctx["posts"])
        print(f"done: {len(events)} events saved")


if __name__ == "__main__":
    main(demo="--demo" in sys.argv)
