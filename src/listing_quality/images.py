"""Image gate: eBay.de needs >= 500 px on the longest side (error 25002 otherwise). Measures the real files (PIL), cached on disk.
Never rewrites URLs; low-resolution images are DROPPED, and a listing without at least one good image is blocked."""
import io
import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / 'data' / 'audit' / 'imgsize.json'
MIN_SIDE = 500


def _load():
    try:
        return json.loads(CACHE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def size(url, fetch=None, cache=None):
    """(w, h) or None when it cannot be measured. fetch/cache are injectable for tests."""
    cache = _load() if cache is None else cache
    if url in cache:
        return tuple(cache[url]) if cache[url] else None
    result = None
    try:
        from PIL import Image
        data = (fetch or (lambda u: requests.get(u, timeout=20).content))(url)
        with Image.open(io.BytesIO(data)) as im:
            result = (im.width, im.height)
    except Exception:
        result = None
    cache[url] = list(result) if result else None
    return result


def good(url, **kw):
    s = size(url, **kw)
    return bool(s) and max(s) >= MIN_SIDE


def filter_urls(urls, **kw):
    """-> (kept, dropped[(url, size)]) keeping order, de-duplicated."""
    cache = kw.pop('cache', None)
    cache = _load() if cache is None else cache
    kept, dropped, seen = [], [], set()
    for u in urls:
        if not u or u in seen:
            continue
        seen.add(u)
        (kept if good(u, cache=cache, **kw) else dropped).append(u if u in kept or good(u, cache=cache, **kw) else (u, cache.get(u)))
    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache), encoding='utf-8')
    except OSError:
        pass
    return kept, dropped
