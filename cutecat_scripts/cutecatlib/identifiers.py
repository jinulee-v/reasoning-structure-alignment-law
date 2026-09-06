"""Catala identifier recognition matching the patched compiler lexer.

The CUTECat lexer accepts an ``XID_Start`` code point followed by
``XID_Continue`` code points or apostrophes.  Python's ``str.isidentifier`` is
defined in terms of the same Unicode XID properties, so use it instead of an
ASCII range or the looser/different regular-expression ``\w`` class.
"""
from __future__ import annotations

from typing import Iterator


def _start(ch: str) -> bool:
    # Python additionally permits underscore as an identifier start; Catala's
    # patched lexer starts with XID_Start, which does not include underscore.
    return ch != "_" and ch.isidentifier()


def _continue(ch: str) -> bool:
    # Prefixing with an XID_Start asks whether `ch` is XID_Continue.  This
    # includes combining marks, Unicode decimal digits, and underscore.
    return ch == "'" or ("a" + ch).isidentifier()


def is_identifier(text: str) -> bool:
    """Whether ``text`` is one unqualified Catala identifier."""
    return bool(text) and _start(text[0]) \
        and all(_continue(ch) for ch in text[1:])


def is_qualified_identifier(text: str) -> bool:
    """Whether ``text`` is one or more dot-separated Catala identifiers."""
    return bool(text) and all(is_identifier(part) for part in text.split("."))


def scan(text: str) -> Iterator[tuple[int, int, str]]:
    """Yield ``(start, end, name)`` for identifiers in a type expression.

    Qualified names are returned as one token. Punctuation and Catala type
    grammar words merely separate tokens.
    """
    i = 0
    while i < len(text):
        if not _start(text[i]):
            i += 1
            continue
        start = i
        i += 1
        while i < len(text) and _continue(text[i]):
            i += 1
        while i < len(text) and text[i] == "." \
                and i + 1 < len(text) and _start(text[i + 1]):
            i += 2
            while i < len(text) and _continue(text[i]):
                i += 1
        yield start, i, text[start:i]
