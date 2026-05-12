"""Fetch a representative image for an item via Serper.dev (Google Images)."""
import logging
import os
from urllib.parse import urlparse

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

SEARCH_ENDPOINT = 'https://google.serper.dev/images'
ALLOWED_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
MAX_BYTES = 5 * 1024 * 1024  # 5 MB ceiling
CANDIDATES = 8
DOWNLOAD_TIMEOUT = 6
BROWSER_UA = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/124.0.0.0 Safari/537.36'
)


def _download_image(url):
    """Return raw bytes for `url` if it's an image under MAX_BYTES, else None."""
    try:
        img = requests.get(
            url,
            timeout=DOWNLOAD_TIMEOUT,
            headers={'User-Agent': BROWSER_UA, 'Accept': 'image/*,*/*;q=0.8'},
            stream=True,
        )
        img.raise_for_status()
        ctype = img.headers.get('Content-Type', '').lower()
        if ctype and not ctype.startswith('image/'):
            return None
        data = img.raw.read(MAX_BYTES + 1, decode_content=True)
        if not data or len(data) > MAX_BYTES:
            return None
        return data
    except Exception as e:
        logger.warning('Image download failed for %s: %s', url, e)
        return None


def fetch_first_image(query):
    """Return (filename, bytes) for the first downloadable Google Images hit, or None."""
    api_key = getattr(settings, 'SERPER_API_KEY', '') or ''
    query = (query or '').strip()
    if not (api_key and query):
        return None

    try:
        resp = requests.post(
            SEARCH_ENDPOINT,
            json={'q': query, 'num': CANDIDATES, 'safe': 'active'},
            headers={
                'X-API-KEY': api_key,
                'Content-Type': 'application/json',
            },
            timeout=5,
        )
        resp.raise_for_status()
        results = resp.json().get('images') or []
    except Exception:
        logger.exception('Serper image search failed for %r', query)
        return None

    for hit in results:
        url = hit.get('imageUrl')
        if not url:
            continue
        data = _download_image(url)
        if data is None:
            continue
        ext = os.path.splitext(urlparse(url).path)[1].lower()
        if ext not in ALLOWED_EXTS:
            ext = '.jpg'
        return (f'auto{ext}', data)

    logger.warning('No downloadable image found for %r (%d candidates)', query, len(results))
    return None
