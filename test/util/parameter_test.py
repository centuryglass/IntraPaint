"""Test Parameter type checking, range and option validation, serialization and input widget selection."""
import json
from copy import deepcopy

from PySide6.QtCore import QSize

from src.ui.input_fields.big_int_spinbox import BigIntSpinbox
from src.ui.input_fields.check_box import CheckBox
from src.ui.input_fields.combo_box import ComboBox
from src.ui.input_fields.dual_toggle import DualToggle
from src.ui.input_fields.line_edit import LineEdit
from src.ui.input_fields.plain_text_edit import PlainTextEdit
from src.ui.input_fields.size_field import SizeField
from src.ui.input_fields.slider_spinbox import IntSliderSpinbox, FloatSliderSpinbox
from src.util.parameter import Parameter, get_parameter_type, TYPE_BOOL, TYPE_INT, TYPE_FLOAT, TYPE_STR, \
    TYPE_QSIZE, TYPE_LIST, TYPE_DICT
from src.util.shared_constants import INT_MAX
from test.base_test_case import IntraPaintTestCase


class TestParameter(IntraPaintTestCase):
    """Test Parameter type checking, range and option validation, serialization and input widget selection."""

    def test_get_parameter_type(self) -> None:
        """Each supported type maps to its type name, with bool checked before int."""
        for value, expected in ((True, TYPE_BOOL), (1, TYPE_INT), (1.0, TYPE_FLOAT), ('', TYPE_STR),
                                (QSize(1, 1), TYPE_QSIZE), ([], TYPE_LIST), ({}, TYPE_DICT)):
            self.assertEqual(get_parameter_type(value), expected, repr(value))
        for value in (None, (1, 2), b'bytes'):
            with self.assertRaises(TypeError, msg=repr(value)):
                get_parameter_type(value)

    def test_constructor_validation(self) -> None:
        """Unknown types, mismatched defaults and range limits on non-numeric types are rejected."""
        with self.assertRaises(ValueError):
            Parameter('p', 'complex')
        with self.assertRaises(TypeError):
            Parameter('p', TYPE_INT, 1.0)
        with self.assertRaises(TypeError):
            Parameter('p', TYPE_STR, minimum=0)
        with self.assertRaises(TypeError):
            Parameter('p', TYPE_INT, minimum=0.0)
        with self.assertRaises(TypeError):
            Parameter('p', TYPE_INT, single_step=0.5)
        with self.assertRaises(TypeError):
            Parameter('p', TYPE_FLOAT, single_step=1)
        with self.assertRaises(AssertionError):
            Parameter('', TYPE_INT)

    def test_validate_type_and_range(self) -> None:
        """Values must match the type and fall within inclusive bounds."""
        param = Parameter('steps', TYPE_INT, 5, minimum=1, maximum=10)
        for value in (1, 5, 10):
            self.assertTrue(param.validate(value), value)
        for value in (0, 11, 5.0, '5', True):
            self.assertFalse(param.validate(value), repr(value))
        with self.assertRaises(ValueError):
            param.validate(11, raise_on_failure=True)
        with self.assertRaises(TypeError):
            param.validate('5', raise_on_failure=True)

    def test_validate_one_sided_range(self) -> None:
        """An unset bound defaults to the type's limit."""
        param = Parameter('scale', TYPE_FLOAT, minimum=0.0)
        self.assertTrue(param.validate(1e6))
        self.assertFalse(param.validate(-0.1))

    def test_validate_qsize_range(self) -> None:
        """Size bounds apply to width and height separately."""
        param = Parameter('size', TYPE_QSIZE, QSize(8, 8), minimum=QSize(8, 8), maximum=QSize(64, 32))
        self.assertTrue(param.validate(QSize(64, 32)))
        self.assertFalse(param.validate(QSize(64, 33)))
        self.assertFalse(param.validate(QSize(7, 32)))

    def test_validate_big_int_accepts_strings(self) -> None:
        """Int parameters with bounds beyond 32 bits convert values with int() first, and reject unparseable ones."""
        param = Parameter('seed', TYPE_INT, 0, minimum=-1, maximum=INT_MAX * 4)
        self.assertTrue(param.validate(str(INT_MAX * 2)))
        self.assertFalse(param.validate('not a number'))
        with self.assertRaises(TypeError):
            param.validate('not a number', raise_on_failure=True)

    def test_valid_options(self) -> None:
        """Only listed options validate, and a default outside the list becomes the first option."""
        param = Parameter('sampler', TYPE_STR, 'c')
        param.set_valid_options(['a', 'b'])
        self.assertEqual(param.default_value, 'a')
        self.assertEqual(param.options, ['a', 'b'])
        self.assertTrue(param.validate('b'))
        self.assertFalse(param.validate('c'))
        with self.assertRaises(ValueError):
            param.validate('c', raise_on_failure=True)

    def test_options_returns_a_copy(self) -> None:
        """Changing the returned options list doesn't change the parameter."""
        param = Parameter('sampler', TYPE_STR)
        self.assertIsNone(param.options)
        param.set_valid_options(['a'])
        options = param.options
        assert options is not None
        options.append('b')
        self.assertEqual(param.options, ['a'])

    def test_invalid_options(self) -> None:
        """Options must match the parameter type and fall within its range."""
        param = Parameter('steps', TYPE_INT, minimum=1, maximum=10)
        with self.assertRaises(TypeError):
            param.set_valid_options(['1'])
        with self.assertRaises(ValueError):
            param.set_valid_options([1, 11])

    def test_serialize_round_trip(self) -> None:
        """Deserializing a serialized parameter restores every field, including QSize values and options."""
        str_param = Parameter('sampler', TYPE_STR, 'b', 'Sampling method')
        str_param.set_valid_options(['a', 'b'])
        size_param = Parameter('size', TYPE_QSIZE, QSize(16, 16), 'Image size', QSize(8, 8), QSize(64, 64), 8)
        size_param.set_valid_options([QSize(8, 8), QSize(16, 16)])
        for param in (Parameter('steps', TYPE_INT, 30, 'Step count', 1, 150, 1),
                      Parameter('cfg', TYPE_FLOAT, 7.5, 'Guidance', 0.0, 30.0, 0.5),
                      Parameter('flag', TYPE_BOOL, True),
                      str_param, size_param):
            serialized = param.serialize()
            restored = Parameter.deserialize(serialized)
            self.assertEqual(restored.serialize(), serialized, param.name)
            self.assertEqual(restored.options, param.options, param.name)
            self.assertEqual(restored.minimum, param.minimum, param.name)
            self.assertEqual(restored.default_value, param.default_value, param.name)

    def test_serialize_format(self) -> None:
        """Serialized QSize values become width/height dicts, and unset fields are omitted."""
        param = Parameter('size', TYPE_QSIZE, QSize(3, 4))
        self.assertEqual(json.loads(param.serialize()), {
            'name': 'size',
            'value_type': TYPE_QSIZE,
            'description': '',
            'default_value': {'width': 3, 'height': 4}
        })

    def test_serialize_validates_value(self) -> None:
        """Serializing with an invalid value raises."""
        param = Parameter('steps', TYPE_INT, minimum=1, maximum=10)
        with self.assertRaises(ValueError):
            param.serialize(11)

    def test_deepcopy(self) -> None:
        """A deep copy has equal fields and an independent options list."""
        param = Parameter('sampler', TYPE_STR, 'a', 'Sampling method')
        param.set_valid_options(['a', 'b'])
        param_copy = deepcopy(param)
        self.assertIsNot(param_copy, param)
        self.assertEqual(param_copy.serialize(), param.serialize())
        param_copy.set_valid_options(['c'])
        self.assertEqual(param.options, ['a', 'b'])

    def test_input_widget_types(self) -> None:
        """Each parameter type and option count gets the matching input widget, with the default value set."""
        two_options = Parameter('mode', TYPE_STR, 'b')
        two_options.set_valid_options(['a', 'b'])
        three_options = Parameter('sampler', TYPE_STR, 'b')
        three_options.set_valid_options(['a', 'b', 'c'])
        cases = (
            (Parameter('steps', TYPE_INT, 3, minimum=1, maximum=10), {}, IntSliderSpinbox, 3),
            (Parameter('seed', TYPE_INT, 3, minimum=-1, maximum=INT_MAX * 4), {}, BigIntSpinbox, None),
            (Parameter('cfg', TYPE_FLOAT, 1.5), {}, FloatSliderSpinbox, 1.5),
            (Parameter('prompt', TYPE_STR, 'text'), {}, LineEdit, 'text'),
            (Parameter('prompt', TYPE_STR, 'text'), {'multi_line': True}, PlainTextEdit, 'text'),
            (Parameter('flag', TYPE_BOOL, True), {}, CheckBox, True),
            (Parameter('size', TYPE_QSIZE, QSize(5, 6)), {}, SizeField, QSize(5, 6)),
            (two_options, {}, DualToggle, 'b'),
            (two_options, {'allow_dual_toggle': False}, ComboBox, 'b'),
            (three_options, {}, ComboBox, 'b'),
        )
        for param, kwargs, widget_type, expected_value in cases:
            widget = param.get_input_widget(**kwargs)
            self.assertIsInstance(widget, widget_type, f'{param.name} {kwargs}')
            if expected_value is not None:
                self.assertEqual(widget.value(), expected_value, f'{param.name} {kwargs}')

    def test_input_widget_tooltip(self) -> None:
        """The description becomes the widget tooltip."""
        widget = Parameter('steps', TYPE_INT, 1, 'Step count').get_input_widget()
        self.assertEqual(widget.toolTip(), 'Step count')

    def test_multi_line_input_widget_requires_free_text(self) -> None:
        """multi_line is rejected for non-string parameters and for option lists."""
        with self.assertRaises(ValueError):
            Parameter('steps', TYPE_INT).get_input_widget(multi_line=True)
        param = Parameter('sampler', TYPE_STR)
        param.set_valid_options(['a', 'b', 'c'])
        with self.assertRaises(ValueError):
            param.get_input_widget(multi_line=True)
