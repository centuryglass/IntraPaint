"""Builds Qt rich text from translated templates and values that may contain markup characters.

Message boxes (`src.ui.modal.modal_utils`) render their messages as rich text, so a layer name, file path or
exception string put into a message must be escaped first, or a `<` or `&` in it is read as markup.
"""
import html
from typing import Iterable


def escape_rich_text(value: object) -> str:
    """Returns `str(value)` with `&`, `<`, `>` and quotes escaped, so it displays as written in rich text."""
    return html.escape(str(value))


def rich_text_format(template: str, **values: object) -> str:
    """Returns `template.format(**values)` with each value escaped by `escape_rich_text`.

    The template's own markup is kept. `int` and `float` values pass through unescaped, so format specs such as
    `{size:.1f}` still apply to them.
    """
    escaped = {key: value if isinstance(value, (int, float)) else escape_rich_text(value)
               for key, value in values.items()}
    return template.format(**escaped)


def rich_text_list(items: Iterable[object]) -> str:
    """Returns a rich-text bulleted list with one escaped entry per item."""
    return '<ul>' + ''.join(f'<li>{escape_rich_text(item)}</li>' for item in items) + '</ul>'
