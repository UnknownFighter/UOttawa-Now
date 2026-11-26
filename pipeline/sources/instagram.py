"""Instagram adapter (instaloader). Works WITHOUT login first. If you add the GitHub secrets
IG_USERNAME + IG_SESSION_B64 (see README) it automatically uses that logged-in session instead."""
import base64
import os
import random
import tempfile
import time
from datetime import timezone

from ..models import Post

_loader = None


def _get_loader():
    global _loader
    if _loader is None:
        import instaloader
        _loader = instaloader.Instaloader(download_pictures=False, download_videos=False, download_video_thumbnails=False,
                                          download_geotags=False, download_comments=False, save_metadata=False,
                                          quiet=True, max_connection_attempts=1)
        user, b64 = os.getenv("IG_USERNAME"), os.getenv("IG_SESSION_B64")
        if user and b64:
            path = os.path.join(tempfile.gettempdir(), f"session-{user}")
            with open(path, "wb") as f:
                f.write(base64.b64decode(b64))
            _loader.load_session_from_file(user, path)
            print("  (using logged-in Instagram session)")
    return _loader


def fetch(account, limit):
    import instaloader
    L = _get_loader()
    handle = account["handle"]
    profile = instaloader.Profile.from_username(L.context, handle)
    posts = []
    for i, p in enumerate(profile.get_posts()):
        if i >= limit:
            break
        urls = [n.display_url for n in p.get_sidecar_nodes()] if p.typename == "GraphSidecar" else [p.url]
        posts.append(Post("instagram", handle, p.shortcode, f"https://www.instagram.com/p/{p.shortcode}/",
                          p.caption or "", p.date_utc.replace(tzinfo=timezone.utc), urls))
        time.sleep(random.uniform(1, 3))          # be gentle: fewer rate-limit blocks
    return {"avatar_url": profile.profile_pic_url}, posts
