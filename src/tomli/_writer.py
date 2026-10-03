# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2021 Taneli Hukkinen
# Licensed to PSF under a Contributor Agreement.

from __future__ import annotations

from datetime import date, datetime, time, timedelta
import re

TYPE_CHECKING = False
if TYPE_CHECKING:
    from typing import IO, Any

_BARE_KEY_RE = re.compile(r"[A-Za-z0-9_-]+")

_BASIC_STR_ESCAPES = {
    "\u0008": r"\b",  # backspace
    "\t": r"\t",  # tab
    "\n": r"\n",  # line feed
    "\u000c": r"\f",  # form feed
    "\r": r"\r",  # carriage return
    '"': r"\"",  # quotation mark
    "\\": r"\\",  # backslash
}


def dumps(__obj: dict[str, Any], /) -> str:
    """Serialize a Python object to a TOML string."""
    if not isinstance(__obj, dict):
        raise TypeError(
            f"TOML document must be a dict, not {type(__obj).__qualname__}"
        )
    lines: list[str] = []
    _emit_table(lines, (), __obj)
    if lines:
        return "\n".join(lines) + "\n"
    return ""


def dump(__fp: IO[str], __obj: dict[str, Any], /) -> None:
    """Serialize a Python object to TOML and write it to a text file object."""
    __fp.write(dumps(__obj))


def _emit_table(
    lines: list[str], path: tuple[str, ...], table: dict[str, Any]
) -> None:
    sub_tables: list[tuple[str, dict[str, Any]]] = []
    array_tables: list[tuple[str, list[dict[str, Any]]]] = []

    # Plain key/value pairs must be emitted before any table headers.
    for key, value in table.items():
        key_str = _render_key(key, path)
        if isinstance(value, dict):
            sub_tables.append((key_str, value))
        elif _is_array_of_tables(value):
            array_tables.append((key_str, value))
        else:
            lines.append(
                f"{key_str} = {_render_value(value, path + (key_str,))}"
            )

    for key, value in sub_tables:
        _emit_header(lines, f"[{_render_path(path + (key,))}]")
        _emit_table(lines, path + (key,), value)

    for key, value in array_tables:
        for element in value:
            _emit_header(lines, f"[[{_render_path(path + (key,))}]]")
            _emit_table(lines, path + (key,), element)


def _emit_header(lines: list[str], header: str) -> None:
    if lines:
        lines.append("")
    lines.append(header)


def _is_array_of_tables(value: Any) -> bool:
    return isinstance(value, list) and len(value) > 0 and all(
        isinstance(element, dict) for element in value
    )


def _render_value(value: Any, path: tuple[str, ...]) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _render_float(value)
    if isinstance(value, str):
        return _render_string(value)
    if isinstance(value, datetime):
        return _render_datetime(value, path)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return _render_time(value, path)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_render_value(v, path) for v in value) + "]"
    if isinstance(value, dict):
        # A dict reached here is nested inside an inline array: it must be
        # rendered as an inline table.
        return _render_inline_table(value, path)
    raise TypeError(
        f"Object of type {type(value).__qualname__!r} is not TOML serializable"
        f" (key: {_render_path(path)!r})"
    )


def _render_inline_table(
    table: dict[str, Any], path: tuple[str, ...]
) -> str:
    parts = []
    for key, value in table.items():
        key_str = _render_key(key, path)
        parts.append(
            f"{key_str} = {_render_value(value, path + (key_str,))}"
        )
    return "{" + ", ".join(parts) + "}"


def _render_float(value: float) -> str:
    rendered = repr(value)
    # `repr()` of a float is always TOML-compatible: it contains either a
    # decimal point, an exponent, or is one of "inf"/"nan".
    return rendered


def _render_datetime(value: datetime, path: tuple[str, ...]) -> str:
    offset = value.utcoffset()
    if offset is not None:
        # TOML offsets are whole minutes between -23:59 and +23:59.
        if (
            abs(offset) >= timedelta(hours=24)
            or offset % timedelta(minutes=1) != timedelta(0)
        ):
            raise TypeError(
                "datetime with a timezone offset that is not a whole number"
                f" of minutes in +/-23:59 is not TOML serializable"
                f" (key: {_render_path(path)!r})"
            )
    return value.isoformat()


def _render_time(value: time, path: tuple[str, ...]) -> str:
    # TOML has no offset time literal.
    if value.tzinfo is not None and value.utcoffset() is not None:
        raise TypeError(
            "timezone-aware time objects are not TOML serializable"
            f" (key: {_render_path(path)!r})"
        )
    return value.isoformat()


def _render_string(value: str) -> str:
    if "\n" in value:
        return _render_multiline_basic_string(value)
    return '"' + _escape_basic_string(value, multiline=False) + '"'


def _render_multiline_basic_string(value: str) -> str:
    body = _escape_basic_string(value, multiline=True)
    # A line ending immediately after the opening delimiter is trimmed by
    # the TOML parser, so duplicate a leading newline to preserve it.
    if value.startswith("\n"):
        body = "\n" + body
    return '"""' + body + '"""'


def _escape_basic_string(value: str, *, multiline: bool) -> str:
    result: list[str] = []
    for char in value:
        if multiline and char == "\n":
            result.append("\n")
            continue
        escape = _BASIC_STR_ESCAPES.get(char)
        if escape is not None:
            result.append(escape)
        else:
            code = ord(char)
            if code < 0x20 or code == 0x7F:
                # Control characters must be written as Unicode escapes.
                result.append(f"\\u{code:04X}")
            else:
                result.append(char)
    return "".join(result)


def _render_key(key: Any, path: tuple[str, ...]) -> str:
    if not isinstance(key, str):
        raise TypeError(
            f"TOML keys must be str, not {type(key).__qualname__}"
            f" (key: {_render_path(path + (str(key),))!r})"
        )
    if _BARE_KEY_RE.fullmatch(key):
        return key
    return '"' + _escape_basic_string(key, multiline=False) + '"'


def _render_path(path: tuple[str, ...]) -> str:
    return ".".join(path)
