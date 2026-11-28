"""TikTok adapter (yt-dlp, metadata only, no login). UNTESTED - TikTok changes often.
Uses the video's cover image for OCR. Add accounts under `tiktok:` in config.yaml."""
from datetime import datetime, timezone

from ..models import Post


def fetch(account, limit, first=False):
    import yt_dlp
    handle = account["handle"]
    opts = {"quiet": True, "skip_download": True, "playlistend": limit, "ignoreerrors": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"https://www.tiktok.com/@{handle}", download=False) or {}
    posts = []
    for e in (info.get("entries") or [])[:limit]:
        if not e:
            continue
        posts.append(Post("tiktok", handle, str(e["id"]), e.get("webpage_url") or f"https://www.tiktok.com/@{handle}/video/{e['id']}",
                          e.get("description") or e.get("title") or "",
                          datetime.fromtimestamp(e.get("timestamp") or 0, tz=timezone.utc),
                          [e["thumbnail"]] if e.get("thumbnail") else []))
    return {"avatar_url": None}, posts
