"""Free, unofficial translation via the deep-translator package (Google's public web endpoint).
If it is unavailable or blocked, we simply return None and the site shows the original text."""


def translate(text, src, dst):
    if not text:
        return None
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source=src, target=dst).translate(text[:4500])
    except Exception:
        return None
