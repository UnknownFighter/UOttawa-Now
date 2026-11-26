"""OCR (Tesseract, free + open source). Runs only in the scheduled job - never for website visitors."""
from io import BytesIO


def ocr_image_url(url):
    try:
        import pytesseract
        import requests
        from PIL import Image
        img = Image.open(BytesIO(requests.get(url, timeout=30).content)).convert("L")
        if img.width < 1000:                      # small text reads better when enlarged
            img = img.resize((img.width * 2, img.height * 2))
        return pytesseract.image_to_string(img, lang="eng+fra")
    except Exception as e:
        print("  OCR failed (is Tesseract installed?):", str(e)[:120])
        return ""


def ocr_post(post):
    if post.ocr_text is not None:
        return post.ocr_text
    return "\n".join(ocr_image_url(u) for u in post.image_urls)
