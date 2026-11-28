"""Instagram adapter using a hosted scraper on Apify (free plan: $5 credit/month, no card).
Runs fine inside GitHub Actions. Needs one secret: APIFY_TOKEN."""
import os
import re
from datetime import datetime

import requests

from ..models import Post

ACTOR = os.getenv("APIFY_ACTOR", "apify~instagram-scraper")   # swap here to try another actor
NEWER_THAN = os.getenv("APIFY_NEWER_THAN", "2 days")           # normal runs only pay for fresh posts


def _images(it):
    urls = list(it.get("images") or [])
    for child in it.get("childPosts") or []:
        if child.get("displayUrl"):
            urls.append(child["displayUrl"])
    if not urls and it.get("displayUrl"):
        urls = [it["displayUrl"]]
    return list(dict.fromkeys(urls))


def fetch(account, limit):
    token = os.getenv("APIFY_TOKEN")
    if not token:
        raise RuntimeError("APIFY_TOKEN is not set")
    handle = account["handle"]
    body = {"directUrls": [f"https://www.instagram.com/{handle}/"],
            "resultsType": "posts", "resultsLimit": limit}
    if limit < 30:                       # a normal run (the first-ever scrape asks for many posts)
        body["onlyPostsNewerThan"] = NEWER_THAN
        body["skipPinnedPosts"] = True   # pinned old posts would otherwise cost credit every run
    r = requests.post(f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items",
                      params={"token": token}, json=body, timeout=330)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Apify HTTP {r.status_code}: {r.text[:200]}")
    items = r.json()
    for it in items:                     # "no_items" just means nothing new; anything else is a real error
        if it.get("error") and it["error"] != "no_items":
            raise RuntimeError(f"Apify: {it.get('errorDescription') or it['error']}")
    posts = []
    for it in items:
        code = it.get("shortCode")
        if not code and it.get("url"):
            m = re.search(r"/(?:p|reel)/([\w-]+)", it["url"])
            code = m.group(1) if m else None
        if not code or not it.get("timestamp"):
            continue
        taken = datetime.fromisoformat(it["timestamp"].replace("Z", "+00:00"))
        posts.append(Post("instagram", handle, code, f"https://www.instagram.com/p/{code}/",
                          it.get("caption") or "", taken, _images(it)))
    avatar = next((it[k] for it in items for k in ("ownerProfilePicUrl", "profilePicUrl") if it.get(k)), None)
    return {"avatar_url": avatar}, posts