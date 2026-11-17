"""Test the rich-text escaping helpers in rich_text."""
from src.util.rich_text import escape_rich_text, rich_text_format, rich_text_list
from test.base_test_case import IntraPaintTestCase


class RichTextTest(IntraPaintTestCase):
    """Test the rich-text escaping helpers in rich_text."""

    def test_escape_rich_text(self) -> None:
        """Markup characters and quotes are escaped, and non-strings are converted first."""
        self.assertEqual('a &lt;b&gt; &amp; &quot;c&quot;', escape_rich_text('a <b> & "c"'))
        self.assertEqual('&lt;lora:x:1&gt;', escape_rich_text(ValueError('<lora:x:1>')))

    def test_format_escapes_values_and_keeps_template_markup(self) -> None:
        """The template's tags stay, while each value displays as written."""
        self.assertEqual('<b>merge</b> layer "a &lt;i&gt;"',
                         rich_text_format('<b>{action}</b> layer "{name}"', action='merge', name='a <i>'))

    def test_format_keeps_number_format_specs(self) -> None:
        """Numbers aren't converted to strings, so their format specs still apply."""
        self.assertEqual('3 frames, 1.5 GB', rich_text_format('{count} frames, {size:.1f} GB', count=3, size=1.53))

    def test_list(self) -> None:
        """Each item becomes an escaped list entry."""
        self.assertEqual('<ul><li>a</li><li>&lt;b&gt;</li></ul>', rich_text_list(['a', '<b>']))
