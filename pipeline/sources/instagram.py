"""Instagram adapter using a hosted scraper on Apify (free plan: $5 credit/month, no card).
Runs fine inside GitHub Actions. Needs one secret: APIFY_TOKEN.
ALL accounts are sent in ONE Apify run (two at most: one for brand-new accounts, one for the rest),
because Apify charges a small fee per run."""
import os
import re
import time
from datetime import datetime

import requests

from ..models import Post

ACTOR = os.getenv("APIFY_ACTOR", "apify~instagram-scraper")   # swap here to try another actor
NEWER_THAN = os.getenv("APIFY_NEWER_THAN", "2 days")           # normal runs only pay for fresh posts
API = "https://api.apify.com/v2"


def _run_actor(token, body):
    """Start an Apify run, wait for it to finish, return its result rows."""
    r = requests.post(f"{API}/acts/{ACTOR}/runs", params={"token": token}, json=body, timeout=60)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Apify HTTP {r.status_code}: {r.text[:200]}")
    run, deadline = r.json()["data"], time.time() + 25 * 60
    while run["status"] in ("READY", "RUNNING"):
        if time.time() > deadline:
            raise RuntimeError("Apify run took longer than 25 minutes")
        time.sleep(10)
        run = requests.get(f"{API}/actor-runs/{run['id']}", params={"token": token}, timeout=60).json()["data"]
    if run["status"] != "SUCCEEDED":
        raise RuntimeError(f"Apify run ended with status {run['status']}")
    r = requests.get(f"{API}/datasets/{run['defaultDatasetId']}/items",
                     params={"token": token, "clean": "true", "format": "json"}, timeout=120)
    return r.json()


def _images(it):
    urls = list(it.get("images") or [])
    for child in it.get("childPosts") or []:
        if child.get("displayUrl"):
            urls.append(child["displayUrl"])
    if not urls and it.get("displayUrl"):
        urls = [it["displayUrl"]]
    return list(dict.fromkeys(urls))


def _owner(it):
    if it.get("ownerUsername"):
        return it["ownerUsername"].lower()
    m = re.search(r"instagram\.com/([\w.]+)", it.get("inputUrl") or "")
    return m.group(1).lower() if m else None


def _scrape_group(token, jobs, first):
    """jobs = [(account, limit)]. Returns {handle: (info, posts)} or {handle: Exception}."""
    out = {a["handle"]: ({}, []) for a, _ in jobs}
    limits = {a["handle"].lower(): lim for a, lim in jobs}
    body = {"directUrls": [f"https://www.instagram.com/{a['handle']}/" for a, _ in jobs],
            "resultsType": "posts", "resultsLimit": max(limits.values())}
    if not first:                        # normal run: only fresh posts
        body["onlyPostsNewerThan"] = NEWER_THAN
        body["skipPinnedPosts"] = True   # pinned old posts would otherwise cost credit every run
    items = _run_actor(token, body)
    by_handle = {a["handle"].lower(): a["handle"] for a, _ in jobs}
    for it in items:
        h = by_handle.get(_owner(it) or "")
        if it.get("error"):
            if it["error"] != "no_items" and h:      # "no_items" just means nothing new
                out[h] = RuntimeError(f"Apify: {it.get('errorDescription') or it['error']}")
            continue
        code = it.get("shortCode")
        if not code and it.get("url"):
            m = re.search(r"/(?:p|reel)/([\w-]+)", it["url"])
            code = m.group(1) if m else None
        if not (h and code and it.get("timestamp")) or isinstance(out[h], Exception):
            continue
        info, posts = out[h]
        if len(posts) >= limits[h.lower()]:
            continue
        info.setdefault("avatar_url", it.get("ownerProfilePicUrl") or it.get("profilePicUrl"))
        posts.append(Post("instagram", h, code, f"https://www.instagram.com/p/{code}/", it.get("caption") or "",
                          datetime.fromisoformat(it["timestamp"].replace("Z", "+00:00")), _images(it),
                          is_video=(it.get("type") == "Video" or it.get("productType") == "clips" or "/reel/" in (it.get("url") or ""))))
    return out


def fetch_many(jobs):
    """jobs = [(account, limit, first)]. One Apify run for the brand-new accounts, one for the others."""
    token = os.getenv("APIFY_TOKEN")
    if not token:
        raise RuntimeError("APIFY_TOKEN is not set")
    results = {}
    for first in (True, False):
        group = [(a, lim) for a, lim, f in jobs if f == first]
        if group:
            results.update(_scrape_group(token, group, first))
    return results


def fetch(account, limit, first=False):
    """Single account (handy for testing)."""
    res = fetch_many([(account, limit, first)])[account["handle"]]
    if isinstance(res, Exception):
        raise res
    return res
