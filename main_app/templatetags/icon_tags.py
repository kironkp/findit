"""Template tag that inlines a vendored Lucide SVG (uses currentColor)."""
import functools
import pathlib

from django import template
from django.conf import settings
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from main_app.icons import ICON_SLUGS

register = template.Library()

_ICON_DIR = pathlib.Path(settings.BASE_DIR) / 'main_app' / 'static' / 'icons'


@functools.lru_cache(maxsize=256)
def _svg_body(slug):
    path = _ICON_DIR / f'{slug}.svg'
    try:
        return path.read_text()
    except OSError:
        return ''


@register.simple_tag
def location_icon(slug, extra_class=''):
    if not slug or slug not in ICON_SLUGS:
        return ''
    svg = _svg_body(slug)
    if not svg:
        return ''
    css_class = 'loc-icon' + (f' {extra_class}' if extra_class else '')
    return format_html(
        '<span class="{}" aria-hidden="true">{}</span>',
        css_class,
        mark_safe(svg),
    )


@register.simple_tag
def location_icon_svg(slug):
    """Raw SVG content only — for places that need the bare SVG (e.g. picker buttons)."""
    if not slug or slug not in ICON_SLUGS:
        return ''
    return mark_safe(_svg_body(slug))
