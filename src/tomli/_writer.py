# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2021 Taneli Hukkinen
# Licensed to PSF under a Contributor Agreement.

from __future__ import annotations

from datetime import date, datetime, time
import re
import string

TYPE_CHECKING = False
if TYPE_CHECKING:
    from typing import Any, Final, IO

    from ._types import Key

BARE_KEY_CHARS: Final = frozenset(string.ascii_letters + string.digits + "-_")

# Escapes valid in both one-line and multiline basic strings.
BASIC_STR_ESCAPES: Final = {
    "\b": "\\b",  # backspace
    "\t": "\\t",  # tab
    "\n": "\\n",  # linefeed
    "\f": "\\f",  # form feed
    "\r": "\\r",  # carriage return
    '"': '\\"',  # quotation mark
    "\\": "\\\\",  # backslash
}

# Three or more quotes in a row would end a multiline basic string, so
# every quote in such a run has to be escaped.
MULTILINE_QUOTE_RUN_RE: Final = re.compile(r'"{3,}')


def dumps(__data: dict[str, Any]) -> str:
    """Serialize a dict to a TOML string."""
    if not isinstance(__data, dict):
        raise TypeError(
            f"Expected a dict at document root, "
            f"not '{type(__data).__qualname__}'"
        )
    lines: list[str] = []
    _dump_table(lines, __data, ())
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def dump(__fp: IO[bytes], __data: dict[str, Any]) -> None:
    """Serialize a dict to TOML and write it to a binary file object."""
    content = dumps(__data).encode()
    try:
        __fp.write(content)
    except TypeError:
        raise TypeError(
            "File must be opened in binary mode, e.g. use `open('foo.toml', 'wb')`"
        ) from None


def _dump_table(lines: list[str], table: dict[str, Any], path: Key) -> None:
    # Key/value pairs must come before any [table] or [[array of tables]]
    # header in a table section, otherwise they'd get assigned to it.
    for key, value in table.items():
        if isinstance(value, dict) or _is_array_of_tables(value):
            continue
        lines.append(
            f"{_format_key_part(key, path)} = {_format_value(value, path + (key,))}"
        )

    for key, value in table.items():
        new_path = path + (key,)
        if isinstance(value, dict):
            _append_header(lines, f"[{_format_key_path(new_path)}]")
            _dump_table(lines, value, new_path)
        elif _is_array_of_tables(value):
            header = f"[[{_format_key_path(new_path)}]]"
            for item in value:
                _append_header(lines, header)
                _dump_table(lines, item, new_path)


def _append_header(lines: list[str], header: str) -> None:
    if lines:
        lines.append("")
    lines.append(header)


def _is_array_of_tables(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) > 0
        and all(isinstance(item, dict) for item in value)
    )


def _format_value(value: Any, path: Key) -> str:
    if isinstance(value, str):
        return _format_str(value)
    if isinstance(value, bool):  # bool must be checked before int
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _format_float(value)
    if isinstance(value, datetime):  # datetime must be checked before date
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        if value.tzinfo is not None and value.utcoffset() is not None:
            raise TypeError(
                "TOML has no offset-aware time type" + _key_suffix(path)
            )
        return value.isoformat()
    if isinstance(value, list):
        return _format_array(value, path)
    if isinstance(value, dict):
        return _format_inline_table(value, path)
    raise TypeError(
        f"Object of type '{type(value).__qualname__}' is not TOML serializable"
        + _key_suffix(path)
    )


def _format_float(value: float) -> str:
    if value != value:
        return "nan"
    if value == float("inf"):
        return "inf"
    if value == float("-inf"):
        return "-inf"
    return repr(value)


def _format_array(value: list[Any], path: Key) -> str:
    if not value:
        return "[]"
    return "[" + ", ".join(_format_value(item, path) for item in value) + "]"


def _format_inline_table(value: dict[str, Any], path: Key) -> str:
    if not value:
        return "{}"
    items = []
    for key, item_value in value.items():
        items.append(
            f"{_format_key_part(key, path)} = "
            f"{_format_value(item_value, path + (key,))}"
        )
    return "{" + ", ".join(items) + "}"


def _format_str(value: str) -> str:
    if "\n" not in value:
        return f'"{_escape_basic(value)}"'
    body = _escape_multiline(value)
    if body.startswith("\n"):
        # The parser trims a newline right after the opening delimiter,
        # so escape a content-leading newline instead of emitting it raw.
        body = "\\n" + body[1:]
    return f'"""{body}"""'


def _escape_basic(value: str) -> str:
    return "".join(_escape_basic_char(char) for char in value)


def _escape_basic_char(char: str) -> str:
    replacement = BASIC_STR_ESCAPES.get(char)
    if replacement is not None:
        return replacement
    if ord(char) < 0x20 or ord(char) == 0x7F:
        return f"\\u{ord(char):04X}"
    return char


def _escape_multiline(value: str) -> str:
    escaped = "".join(_escape_multiline_char(char) for char in value)
    return MULTILINE_QUOTE_RUN_RE.sub(
        lambda match: '\\"' * len(match.group(0)), escaped
    )


def _escape_multiline_char(char: str) -> str:
    if char in ("\t", "\n", '"'):
        return char
    return _escape_basic_char(char)


def _format_key_path(path: Key) -> str:
    return ".".join(_format_key_part(part, ()) for part in path)


def _format_key_part(part: Any, parent_path: Key) -> str:
    if not isinstance(part, str):
        raise TypeError(
            f"TOML keys must be str, got {part!r}" + _key_suffix(parent_path)
        )
    if part and BARE_KEY_CHARS.issuperset(part):
        return part
    return f'"{_escape_basic(part)}"'


def _key_suffix(path: Key) -> str:
    if not path:
        return " (at document root)"
    return f" (at key {'.'.join(path)!r})"
