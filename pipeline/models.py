"""Shared data structure: one scraped social-media post."""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Post:
    platform: str            # "instagram" or "tiktok"
    handle: str              # account handle without the @
    post_id: str
    url: str                 # link to the original post
    caption: str
    taken_at: datetime       # timezone-aware
    image_urls: list = field(default_factory=list)  # images to run OCR on
    ocr_text: str = None     # only used by the demo (pre-supplied OCR text, skips real OCR)
