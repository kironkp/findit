"""Whisper transcription + GPT structured-extraction for bulk item entry."""
import json
import logging

from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

_PARSE_MODEL = 'gpt-4o-mini'
_TRANSCRIBE_MODEL = 'whisper-1'


def _client():
    api_key = getattr(settings, 'OPENAI_API_KEY', '') or ''
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def transcribe(file_obj, filename='audio.webm'):
    """Run Whisper on an uploaded audio file. Returns transcript text or None."""
    client = _client()
    if not client:
        return None
    try:
        # The SDK accepts a (filename, fileobj) tuple for unknown content types.
        resp = client.audio.transcriptions.create(
            model=_TRANSCRIBE_MODEL,
            file=(filename, file_obj),
        )
        return (resp.text or '').strip()
    except Exception:
        logger.exception('Whisper transcription failed')
        return None


PARSE_SYSTEM = (
    "You are helping a user add items to their personal inventory app. "
    "Read the user's freeform description of things they own and where they are, "
    "then return a JSON object with a single key `items` whose value is a JSON array. "
    "Each element has fields: "
    "`name` (concise item name, max 80 chars, no quantity prefix), "
    "`distinguishing_detail` (any specific detail that sets it apart, or empty string), "
    "`quantity` (positive integer, default 1), "
    "`location_suggestion` (the location the user implied, expressed as a nested path "
    "using ' > ' as separator, deepest segment last — e.g. 'Garage > Left Wall' or "
    "'Studio A > Indigo Box'. Match an existing path verbatim when the user clearly "
    "refers to it. If the user describes a sub-location inside an existing parent, keep "
    "the existing parent name in the path and append the new child. Empty string if no "
    "location is mentioned), "
    "`location_icons` (a JSON object mapping EACH segment name in `location_suggestion` "
    "to the icon slug from the provided catalog that best fits THAT segment. Example: "
    "for location_suggestion='Indigo > Starboard Cockpit Locker', use "
    "{'Indigo': 'sailboat', 'Starboard Cockpit Locker': 'box'}. Use only slugs in the "
    "catalog; omit a segment if no good match. Empty object {} if no location suggested). "
    "Do not invent items the user didn't describe. If the user repeats themselves, "
    "merge duplicates by adjusting quantity."
)


def parse_items(text, existing_locations, icon_slugs=None):
    """Parse a freeform description into a list of item dicts. Returns [] on any failure.

    `existing_locations` is an iterable of hierarchical path strings like
    "Garage > Left Wall" — pass these so the model can reuse paths verbatim.
    `icon_slugs` is an iterable of available icon slugs the model can pick from.
    """
    client = _client()
    text = (text or '').strip()
    if not (client and text):
        return []

    loc_lines = '\n'.join(f'- {p}' for p in existing_locations) or '(none yet)'
    icons_line = ', '.join(sorted(icon_slugs or [])) or '(none)'
    user_msg = (
        f"Existing location paths (use these verbatim when they apply):\n{loc_lines}\n\n"
        f"Icon catalog (pick `location_icon` from these slugs only):\n{icons_line}\n\n"
        f"User said:\n{text}"
    )

    try:
        resp = client.chat.completions.create(
            model=_PARSE_MODEL,
            messages=[
                {'role': 'system', 'content': PARSE_SYSTEM},
                {'role': 'user', 'content': user_msg},
            ],
            response_format={'type': 'json_object'},
            temperature=0.2,
        )
        raw = resp.choices[0].message.content or '{}'
        data = json.loads(raw)
    except Exception:
        logger.exception('GPT item parse failed')
        return []

    items = data.get('items') if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []

    cleaned = []
    for it in items:
        if not isinstance(it, dict):
            continue
        name = (it.get('name') or '').strip()[:80]
        if not name:
            continue
        try:
            qty = int(it.get('quantity') or 1)
        except (TypeError, ValueError):
            qty = 1
        icons_raw = it.get('location_icons') or {}
        icon_map = {}
        if isinstance(icons_raw, dict):
            for seg, slug in icons_raw.items():
                if not isinstance(seg, str) or not isinstance(slug, str):
                    continue
                icon_map[seg.strip()] = slug.strip()[:40]
        cleaned.append({
            'name': name,
            'distinguishing_detail': (it.get('distinguishing_detail') or '').strip()[:200],
            'quantity': max(1, qty),
            'location_suggestion': (it.get('location_suggestion') or '').strip()[:200],
            'location_icons': icon_map,
        })
    return cleaned
