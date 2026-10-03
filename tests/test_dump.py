# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2021 Taneli Hukkinen
# Licensed to PSF under a Contributor Agreement.

import datetime
from decimal import Decimal
import io
import math
from pathlib import Path
import unittest

from . import tomllib

DATA_DIR = Path(__file__).parent / "data"
VALID_FILES = tuple((DATA_DIR / "valid").glob("**/*.toml"))


def assert_roundtrip(test_case, data):
    text = tomllib.dumps(data)
    actual = tomllib.loads(text)
    test_case.assertEqual(actual, data, msg=f"dumped TOML:\n{text}")
    return text


class TestDumps(unittest.TestCase):
    def test_user_example(self):
        data = {
            "title": "a\nb",
            "when": datetime.datetime(
                2024, 5, 1, 9, 30, tzinfo=datetime.timezone.utc
            ),
        }
        text = tomllib.dumps(data)
        self.assertEqual(tomllib.loads(text), data)

    def test_basic_string_escapes(self):
        data = {
            "newline": "a\nb",
            "tab": "a\tb",
            "backslash": "a\\b",
            "quote": 'a"b',
            "carriage": "a\rb",
            "backspace": "a\bb",
            "formfeed": "a\fb",
            "control": "a\x00\x1f\x7fb",
            "unicode": "åäö 中文字符 🎉",
        }
        text = assert_roundtrip(self, data)
        # Control characters must not appear literally
        self.assertNotIn("\x00", text)
        self.assertNotIn("\x7f", text)
        self.assertNotIn("\t", text.split("\n")[0])

    def test_multiline_string(self):
        data = {
            "leading_newline": "\nfirst\nsecond",
            "trailing_newline": "first\nsecond\n",
            "quotes": 'he said "hi"\nand left',
            "triple_quote": 'a"""b\nc',
            "backslash": "a\\\nb",
            "ends_with_quote": 'foo\nbar"',
            "ends_with_two_quotes": 'foo\nbar""',
            "crlf": "a\r\nb",
        }
        text = assert_roundtrip(self, data)
        self.assertIn('"""', text)

    def test_dates_and_times(self):
        data = {
            "dt_utc": datetime.datetime(
                2024, 5, 1, 9, 30, tzinfo=datetime.timezone.utc
            ),
            "dt_offset": datetime.datetime(
                2024,
                5,
                1,
                9,
                30,
                15,
                123456,
                tzinfo=datetime.timezone(datetime.timedelta(hours=5, minutes=30)),
            ),
            "dt_negative_offset": datetime.datetime(
                2024,
                5,
                1,
                9,
                30,
                tzinfo=datetime.timezone(-datetime.timedelta(hours=8)),
            ),
            "dt_naive": datetime.datetime(2024, 5, 1, 9, 30),
            "date": datetime.date(2024, 5, 1),
            "time": datetime.time(9, 30, 15, 123456),
            "time_no_micros": datetime.time(9, 30),
        }
        text = assert_roundtrip(self, data)
        self.assertIn("+05:30", text)
        self.assertIn("-08:00", text)

    def test_datetime_with_offset_seconds_not_serializable(self):
        class WeirdZone(datetime.tzinfo):
            def utcoffset(self, dt):
                return datetime.timedelta(hours=5, minutes=30, seconds=45)

            def tzname(self, dt):
                return "weird"

            def dst(self, dt):
                return datetime.timedelta(0)

        data = {"when": datetime.datetime(2024, 5, 1, 9, 30, tzinfo=WeirdZone())}
        with self.assertRaises(TypeError) as exc_info:
            tomllib.dumps(data)
        self.assertIn("when", str(exc_info.exception))

    def test_aware_time_not_serializable(self):
        data = {
            "t": datetime.time(9, 30, tzinfo=datetime.timezone.utc),
        }
        with self.assertRaises(TypeError) as exc_info:
            tomllib.dumps(data)
        self.assertIn("t", str(exc_info.exception))

    def test_floats(self):
        data = {
            "a": 0.1,
            "b": 1e16,
            "c": 1e-05,
            "d": -0.0,
            "e": 10.0,
            "f": float("inf"),
            "g": float("-inf"),
            "h": 3.141592653589793,
        }
        assert_roundtrip(self, data)

    def test_float_nan(self):
        text = tomllib.dumps({"nan": float("nan")})
        self.assertTrue(math.isnan(tomllib.loads(text)["nan"]))

    def test_float_parse_float_roundtrip(self):
        data = {"a": 0.1, "b": [1.5, 2.25]}
        text = tomllib.dumps(data)
        parsed = tomllib.loads(text, parse_float=Decimal)
        self.assertEqual(parsed["a"], Decimal("0.1"))
        self.assertEqual(parsed["b"], [Decimal("1.5"), Decimal("2.25")])

    def test_ints_and_bools(self):
        data = {
            "zero": 0,
            "neg": -42,
            "big": 2**100,
            "t": True,
            "f": False,
        }
        assert_roundtrip(self, data)

    def test_nested_tables(self):
        data = {
            "a": {"b": {"c": 1, "d": "x"}, "e": [1, 2]},
            "f": "top",
        }
        text = assert_roundtrip(self, data)
        self.assertIn("[a.b]", text)

    def test_array_of_tables(self):
        data = {
            "products": [
                {"name": "Hammer", "sku": 738594937},
                {"name": "Nail", "sku": 284758393},
            ],
        }
        text = assert_roundtrip(self, data)
        self.assertIn("[[products]]", text)
        self.assertNotIn("[{", text)

    def test_array_of_tables_with_sub_tables(self):
        data = {
            "fruit": [
                {
                    "name": "apple",
                    "physical": {"color": "red", "shape": "round"},
                    "variety": [{"name": "red delicious"}, {"name": "granny smith"}],
                },
                {"name": "banana", "variety": [{"name": "plantain"}]},
            ],
        }
        text = assert_roundtrip(self, data)
        self.assertIn("[[fruit]]", text)
        self.assertIn("[fruit.physical]", text)
        self.assertIn("[[fruit.variety]]", text)

    def test_empty_structures(self):
        data = {
            "empty_table": {},
            "empty_array": [],
            "nested": {"also_empty": {}},
            "array_of_empty_tables": [{}],
        }
        assert_roundtrip(self, data)

    def test_empty_document(self):
        self.assertEqual(tomllib.loads(tomllib.dumps({})), {})

    def test_quoted_keys(self):
        data = {
            "a.b": 1,
            "with space": 2,
            "": 3,
            'quote"key': 4,
            "back\\slash": 5,
            "ʎǝʞ": 6,
            "normal_key-1": 7,
            "table": {"weird.key": {"deeper": 8}},
        }
        text = assert_roundtrip(self, data)
        self.assertIn('"a.b"', text)
        self.assertIn('"ʎǝʞ"', text)

    def test_arrays(self):
        data = {
            "ints": [1, 2, 3],
            "mixed": [1, "two", 3.0, True],
            "nested": [[1, 2], [3]],
            "table_in_nested_array": [[{"a": 1}, {"b": 2}]],
            "table_among_scalars": [1, {"b": 2}],
            "array_of_tables": [{"a": 1}, {"b": 2}],
            "empty": [],
        }
        text = assert_roundtrip(self, data)
        # Dicts nested inside arrays must use inline tables
        self.assertIn("{a = 1}", text)
        self.assertIn("{b = 2}", text)
        # A direct list of dicts is an array of tables
        self.assertIn("[[array_of_tables]]", text)

    def test_unsupported_types(self):
        for bad_value in (None, {1, 2}, object(), b"bytes"):
            with self.subTest(bad_value=bad_value):
                with self.assertRaises(TypeError) as exc_info:
                    tomllib.dumps({"section": {"the_key": bad_value}})
                self.assertIn("section.the_key", str(exc_info.exception))

    def test_non_string_key(self):
        with self.assertRaises(TypeError):
            tomllib.dumps({1: "one"})

    def test_non_dict_document(self):
        with self.assertRaises(TypeError):
            tomllib.dumps([1, 2, 3])

    def test_dump_to_file(self):
        data = {"a": 1, "b": {"c": "x"}}
        fp = io.StringIO()
        tomllib.dump(fp, data)
        self.assertEqual(tomllib.loads(fp.getvalue()), data)

    def test_valid_data_files_roundtrip(self):
        for valid in VALID_FILES:
            with self.subTest(msg=valid.stem):
                toml_str = valid.read_bytes().decode()
                try:
                    data = tomllib.loads(toml_str)
                except tomllib.TOMLDecodeError:
                    continue
                dumped = tomllib.dumps(data)
                actual = tomllib.loads(dumped)
                self.assertEqual(
                    _normalize(actual),
                    _normalize(data),
                    msg=f"dumped TOML:\n{dumped}",
                )


def _normalize(obj):
    """Make NaN compare equal to itself for test purposes."""
    if isinstance(obj, float) and math.isnan(obj):
        return "nan"
    if isinstance(obj, list):
        return [_normalize(item) for item in obj]
    if isinstance(obj, dict):
        return {key: _normalize(value) for key, value in obj.items()}
    return obj
