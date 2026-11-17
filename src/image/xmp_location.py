"""Finds and removes the place properties of an XMP packet.

The packet is edited as text, not parsed, so everything outside the removed properties keeps its exact bytes, and an
untrusted packet is never handed to an XML parser. Properties are matched by namespace URI, so any prefix works.
"""
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

_NS_EXIF = 'http://ns.adobe.com/exif/1.0/'
_NS_EXIF_EX = 'http://cipa.jp/exif/1.0/'
_NS_PHOTOSHOP = 'http://ns.adobe.com/photoshop/1.0/'
_NS_IPTC_CORE = 'http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/'
_NS_IPTC_EXT = 'http://iptc.org/std/Iptc4xmpExt/2008-02-29/'

# Regular expressions for the local names of place properties, by namespace URI. Free text such as a caption or a
# keyword can name a place too, and isn't touched:
LOCATION_PROPERTIES = {
    _NS_EXIF: r'GPS\w*',
    _NS_EXIF_EX: r'GPS\w*',
    _NS_PHOTOSHOP: r'City|State|Country',
    _NS_IPTC_CORE: r'Location|CountryCode',
    _NS_IPTC_EXT: r'LocationShown|LocationCreated',
}

_NAMESPACE_DECLARATION = re.compile(r'xmlns:([\w.\-]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\')')
_UTF_8 = 'utf-8'


def _location_name_pattern(text: str) -> Optional[str]:
    """Returns a regular expression matching the qualified name of any place property, or None if there are none.

    A prefix can be declared for different URIs in different elements, which this doesn't track. A prefix counts as a
    place property's prefix if any declaration binds it to that namespace.
    """
    prefixes: dict[str, set[str]] = {}
    for match in _NAMESPACE_DECLARATION.finditer(text):
        uri = match.group(2) if match.group(2) is not None else match.group(3)
        if uri in LOCATION_PROPERTIES:
            prefixes.setdefault(uri, set()).add(match.group(1))
    names = [f'{re.escape(prefix)}:(?:{LOCATION_PROPERTIES[uri]})'
             for uri, uri_prefixes in prefixes.items() for prefix in sorted(uri_prefixes)]
    return None if len(names) == 0 else '|'.join(names)


def _patterns(text: str) -> list[re.Pattern[str]]:
    """Returns the patterns for a place property written as an element, then as an attribute."""
    names = _location_name_pattern(text)
    if names is None:
        return []
    element = re.compile(rf'<(?P<name>{names})(?=[\s/>])[^>]*?(?:/>|>.*?</(?P=name)\s*>)', re.DOTALL)
    attribute = re.compile(rf'\s(?:{names})\s*=\s*(?:"[^"]*"|\'[^\']*\')')
    return [element, attribute]


def _decode(packet: str | bytes) -> Optional[str]:
    if isinstance(packet, str):
        return packet
    try:
        return packet.decode(_UTF_8)
    except UnicodeDecodeError:
        logger.warning('XMP packet is not UTF-8, so its location fields can\'t be checked')
        return None


def has_xmp_location(packet: str | bytes) -> bool:
    """Whether the packet holds any place property: GPS fields, city, state, country or a named location."""
    text = _decode(packet)
    return text is not None and any(pattern.search(text) is not None for pattern in _patterns(text))


def remove_xmp_location(packet: str | bytes) -> str | bytes:
    """Returns the packet without its place properties, as the same type it was given.

    A packet that isn't UTF-8 is returned unchanged.
    """
    text = _decode(packet)
    if text is None:
        return packet
    for pattern in _patterns(text):
        text = pattern.sub('', text)
    return text if isinstance(packet, str) else text.encode(_UTF_8)
