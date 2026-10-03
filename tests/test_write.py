# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2021 Taneli Hukkinen
# Licensed to PSF under a Contributor Agreement.

import datetime
from decimal import Decimal
import io
import math
import unittest

from . import tomllib


class TestRoundTrip(unittest.TestCase):
    def assertRoundTrip(self, data):
        text = tomllib.dumps(data)
        self.assertEqual(tomllib.loads(text), data)
        return text

    def test_basic(self):
        self.assertRoundTrip(
            {
                "title": "a\nb",
                "when": datetime.datetime(
                    2024, 5, 1, 9, 30, tzinfo=datetime.timezone.utc
                ),
            }
        )

    def test_empty_document(self):
        self.assertEqual(tomllib.dumps({}), "")
        self.assertRoundTrip({})

    def test_empty_table_and_array(self):
        self.assertRoundTrip({"a": {}, "b": [], "c": {"d": {}}, "e": [[]]})

    def test_basic_string_escapes(self):
        self.assertRoundTrip(
            {"s": "tab\tnl-ish\\n quote\" backslash\\ ctrl\x00\x1f\x7f\b\f\r"}
        )

    def test_multiline_string(self):
        text = self.assertRoundTrip({"s": "line one\nline two\n"})
        self.assertIn('"""', text)

    def test_multiline_string_leading_newline(self):
        self.assertRoundTrip({"s": "\nstarts with newline"})
        self.assertRoundTrip({"s": "\n"})

    def test_multiline_string_quotes(self):
        self.assertRoundTrip({"s": 'has """ triple quotes\ninside'})
        self.assertRoundTrip({"s": 'ends with quote"\n'})
        self.assertRoundTrip({"s": 'ends with quotes""\n'})
        self.assertRoundTrip({"s": 'a"\nb"\nc'})

    def test_dates_and_times(self):
        self.assertRoundTrip(
            {
                "date": datetime.date(2024, 2, 29),
                "time": datetime.time(23, 59, 1, 123456),
                "naive": datetime.datetime(1988, 10, 27, 9, 30),
                "utc": datetime.datetime(
                    2024, 5, 1, 9, 30, tzinfo=datetime.timezone.utc
                ),
                "offset": datetime.datetime(
                    2024,
                    5,
                    1,
                    9,
                    30,
                    tzinfo=datetime.timezone(datetime.timedelta(hours=5, minutes=30)),
                ),
                "negative_offset": datetime.datetime(
                    2024,
                    5,
                    1,
                    9,
                    30,
                    tzinfo=datetime.timezone(-datetime.timedelta(hours=8)),
                ),
            }
        )

    def test_aware_time_not_serializable(self):
        aware = datetime.time(9, 30, tzinfo=datetime.timezone.utc)
        with self.assertRaises(TypeError):
            tomllib.dumps({"t": aware})

    def test_floats(self):
        self.assertRoundTrip({"f": [0.1, 1e300, -0.0, 1.5e-7, 3.0]})
        self.assertRoundTrip({"inf": float("inf"), "ninf": float("-inf")})
        result = tomllib.loads(tomllib.dumps({"nan": float("nan")}))
        self.assertTrue(math.isnan(result["nan"]))

    def test_floats_with_parse_float(self):
        result = tomllib.loads(tomllib.dumps({"f": 0.1}), parse_float=Decimal)
        self.assertEqual(result, {"f": Decimal("0.1")})

    def test_nested_tables(self):
        text = self.assertRoundTrip({"a": {"b": {"c": 1}, "d": 2}, "e": 3})
        self.assertIn("[a]", text)
        self.assertIn("[a.b]", text)

    def test_array_of_tables(self):
        text = self.assertRoundTrip({"items": [{"a": 1}, {"a": 2}, {}]})
        self.assertEqual(text.count("[[items]]"), 3)
        self.assertNotIn("items = [", text)

    def test_nested_array_of_tables(self):
        text = self.assertRoundTrip(
            {"a": [{"sub": [{"c": 1}, {"c": 2}], "v": 1}, {"sub": []}]}
        )
        self.assertIn("[[a.sub]]", text)

    def test_mixed_array_uses_inline_tables(self):
        self.assertRoundTrip({"mixed": [1, "a", {"inline": True}, [1.5], {}]})

    def test_quoted_keys(self):
        text = self.assertRoundTrip(
            {
                "key with spaces": 1,
                "key.with.dots": 2,
                'key"quote': 3,
                "": 4,
                "键": 5,
                "table": {"sub key": 6},
            }
        )
        self.assertIn('"key with spaces" = 1', text)
        self.assertIn('"key.with.dots" = 2', text)

    def test_scalars(self):
        self.assertRoundTrip(
            {"bool": True, "neg": -42, "big": 2**63, "zero": 0, "s": ""}
        )

    def test_unsupported_type_raises_with_key(self):
        with self.assertRaises(TypeError) as exc_info:
            tomllib.dumps({"a": {"b": {1, 2}}})
        self.assertIn("a.b", str(exc_info.exception))

    def test_none_raises(self):
        with self.assertRaises(TypeError):
            tomllib.dumps({"nothing": None})

    def test_non_dict_root_raises(self):
        with self.assertRaises(TypeError):
            tomllib.dumps([1, 2])
        with self.assertRaises(TypeError):
            tomllib.dumps("str")

    def test_non_str_key_raises(self):
        with self.assertRaises(TypeError) as exc_info:
            tomllib.dumps({"a": {1: "x"}})
        self.assertIn("a", str(exc_info.exception))


class TestDump(unittest.TestCase):
    def test_dump_binary_file(self):
        data = {"a": 1, "b": {"c": "x"}}
        buf = io.BytesIO()
        tomllib.dump(buf, data)
        buf.seek(0)
        self.assertEqual(tomllib.load(buf), data)

    def test_dump_text_file_raises(self):
        with self.assertRaises(TypeError):
            tomllib.dump(io.StringIO(), {"a": 1})


if __name__ == "__main__":
    unittest.main()
