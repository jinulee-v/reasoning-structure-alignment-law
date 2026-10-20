"""Read values from BOBCat JSON models and legacy Catala result output.

New BOBCat examples use its machine-readable JSON model/replay protocol.
The pretty-printer parser remains for old captures and interpreter output. Its
accepted grammar is:

    true | false                      LBool
    -12                               LInt
    -1.25 | 1.333…                    LRat --- the ellipsis marks a decimal
                                      truncated at --max-prec-digits, so the
                                      value that was printed is not the value
                                      that was computed
    ¤42.00                            LMoney, always exactly two decimals
    |2024-01-01|                      LDate (years may exceed four digits)
    [0 years, 0 months, 3 days]       LDuration
    ()                                LUnit
    [a; b; c]                         EArray  --- semicolons, unlike a duration
    { Name f = v; g = w; } | {Name}   EStruct
    Cons | Cons v                     EInj, nullary and with a payload
    (a, b)                            ETuple
    ⟨v⟩                                 EPureDefault
    ∅                                   EEmpty
    λ (x: T) → ...                      function value (kept opaque)

Two things are deliberately *not* undone here.  A money value keeps its two
decimals as a `Decimal`, because it is a number of cents and rounding it to a
float would be a lie about a fee.  And a truncated decimal is flagged rather
than silently accepted --- `Value.exact` is false for it, and
`dataset.py` counts them, because a dataset row whose number was printed with
an ellipsis is not a row anything should be trained or tested against.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from . import identifiers


class ParseError(ValueError):
    """Raised on a printed value this module does not know how to read."""


@dataclass
class Value:
    """One parsed value: a JSON-able tree, its Catala shape, and its text.

    `raw` is kept because it is the only thing that is certainly faithful ---
    everything else in this dataclass is this module's reading of it.
    """
    py: Any                      # bool / int / Decimal / str / list / dict
    kind: str                    # boolean|integer|decimal|money|date|duration|
                                 # unit|array|struct|enum|tuple|function
    raw: str
    exact: bool = True           # False if a decimal was printed truncated

    def as_json(self) -> Any:
        """The value as it goes into the JSONL, Decimals rendered as strings.

        `json` would happily write a Decimal as a float; a fee of ¤50.00 must
        not become 50.000000000000007 on the way to a file.
        """
        return _json_of(self.py)


def from_json(value: Any) -> Value:
    """Wrap a value already validated against Catala's input JSON schema.

    BOBCat emits solver models in that schema and then replays the exact same
    object in the reference interpreter.  Unlike the legacy pretty-printer
    parser, this path therefore does not need to guess whether a JSON string is
    a date, money amount, decimal, or nullary enum constructor.
    """
    if isinstance(value, bool):
        kind = "boolean"
    elif isinstance(value, int):
        kind = "integer"
    elif isinstance(value, float):
        kind = "json-number"
    elif isinstance(value, list):
        kind = "array"
    elif isinstance(value, dict):
        kind = "struct"
    elif value is None:
        kind = "empty"
    else:
        kind = "json-string"
    return Value(value, kind, repr(value), True)


def _json_of(v: Any) -> Any:
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, list):
        return [_json_of(x) for x in v]
    if isinstance(v, dict):
        return {k: _json_of(x) for k, x in v.items()}
    return v


# ---- tokenizer -----------------------------------------------------------
# `|` delimits a date on both sides, so dates are lexed whole rather than as
# three integers around two bars.  `_Lexer` validates the broad identifier token
# below against Unicode XID_Start/XID_Continue, as the patched compiler lexer
# does (apostrophe extension included).
_TOKEN = re.compile(r"""
      # Catala uses proleptic Gregorian dates and may print years at or before
      # year zero (for example, `|-400-12-31|`) for solver-generated inputs.
      (?P<date>\|(?:\d{4,}|-\d+)-\d{2}-\d{2}\|)
    | (?P<empty>∅)
    | (?P<money>¤-?\d+\.\d+)
    # An integral decimal prints as `0.`, so the fractional part may be empty.
    | (?P<decimal>-?\d+\.\d*…?)
    | (?P<integer>-?\d+)
    | (?P<ident>[^\s{}\[\]();,=⟨⟩]+)
    | (?P<punct>[{}\[\]();,=⟨⟩])
    | (?P<space>\s+)
""", re.VERBOSE)


@dataclass
class _Lexer:
    text: str
    pos: int = 0
    toks: list = field(default_factory=list)
    i: int = 0

    def __post_init__(self):
        pos = 0
        while pos < len(self.text):
            m = _TOKEN.match(self.text, pos)
            if m is None:
                raise ParseError(
                    f"cannot tokenize {self.text[pos:pos+20]!r} "
                    f"at offset {pos} of {self.text!r}")
            pos = m.end()
            if m.lastgroup == "ident" \
                    and not identifiers.is_qualified_identifier(m.group()):
                raise ParseError(
                    f"invalid identifier {m.group()!r} at offset {m.start()} "
                    f"of {self.text!r}")
            if m.lastgroup != "space":
                self.toks.append((m.lastgroup, m.group()))

    def peek(self, ahead: int = 0):
        j = self.i + ahead
        return self.toks[j] if j < len(self.toks) else (None, None)

    def next(self):
        tok = self.peek()
        self.i += 1
        return tok

    def expect(self, text: str):
        kind, val = self.next()
        if val != text:
            raise ParseError(f"expected {text!r}, found {val!r} in {self.text!r}")


def parse(text: str) -> Value:
    """Parse one printed value.  Raises `ParseError` on anything unexpected."""
    text = text.strip()
    # Catala scopes may expose internal function-valued variables. The pretty
    # printer renders their evaluated closure rather than a serialisable Catala
    # datum. Preserve that rendering losslessly instead of attempting to parse
    # the expression language as a value tree.
    if text.startswith("λ "):
        return Value(text, "function", text)
    lx = _Lexer(text)
    v = _value(lx)
    if lx.i != len(lx.toks):
        raise ParseError(f"trailing {lx.peek()[1]!r} in {text!r}")
    return v


def _value(lx: _Lexer) -> Value:
    kind, val = lx.peek()
    if kind is None:
        raise ParseError(f"empty value in {lx.text!r}")

    if kind == "date":
        lx.next()
        return Value(val[1:-1], "date", val)
    if kind == "money":
        lx.next()
        return Value(Decimal(val[1:]), "money", val)
    if kind == "decimal":
        lx.next()
        exact = not val.endswith("…")
        return Value(Decimal(val.rstrip("…")), "decimal", val, exact)
    if kind == "integer":
        lx.next()
        return Value(int(val), "integer", val)
    if kind == "empty":
        lx.next()
        return Value(None, "empty", val)
    if kind == "ident":
        if val in ("true", "false"):
            lx.next()
            return Value(val == "true", "boolean", val)
        return _enum(lx)
    if val == "[":
        return _bracketed(lx)
    if val == "{":
        return _struct(lx)
    if val == "(":
        return _paren(lx)
    if val == "⟨":
        return _pure_default(lx)
    raise ParseError(f"unexpected {val!r} in {lx.text!r}")


def _pure_default(lx: _Lexer) -> Value:
    """A fully resolved default value, printed as `⟨value⟩`."""
    start = lx.i
    lx.expect("⟨")
    value = _value(lx)
    lx.expect("⟩")
    return Value({"default": value.py}, "default", _slice(lx, start),
                 value.exact)


def _enum(lx: _Lexer) -> Value:
    """`Cons`, or `Cons payload`.

    A constructor is followed by its payload iff the next token can start a
    value and is not something that closes or separates the construct we are
    inside.  Enum-of-enum (`Some Present`) reads right, because the payload is
    parsed as a whole value before this returns.
    """
    _, cons = lx.next()
    kind, val = lx.peek()
    if kind is None or val in (";", ",", "}", "]", ")", "="):
        return Value({"cons": cons}, "enum", cons)
    payload = _value(lx)
    return Value({"cons": cons, "payload": payload.py}, "enum",
                 f"{cons} {payload.raw}", payload.exact)


def _bracketed(lx: _Lexer) -> Value:
    """`[a; b]` is an array; `[0 years, 0 months, 3 days]` is a duration.

    The printer gives them the same brackets and different separators, so the
    duration is recognized by its shape and everything else is an array.
    """
    start = lx.i
    lx.expect("[")
    dur = _try_duration(lx)
    if dur is not None:
        return dur
    lx.i = start + 1

    items: list = []
    exact = True
    if lx.peek()[1] != "]":
        while True:
            v = _value(lx)
            items.append(v.py)
            exact = exact and v.exact
            if lx.peek()[1] == ";":
                lx.next()
                continue
            break
    lx.expect("]")
    return Value(items, "array", _slice(lx, start), exact)


def _try_duration(lx: _Lexer):
    want = ["years", "months", "days"]
    got = []
    start = lx.i - 1
    for n, unit in enumerate(want):
        kind, val = lx.next()
        if kind != "integer":
            return None
        got.append(int(val))
        kind, word = lx.next()
        if word != unit:
            return None
        if n < 2 and lx.peek()[1] != ",":
            return None
        if n < 2:
            lx.next()
    if lx.peek()[1] != "]":
        return None
    lx.next()
    y, m, d = got
    return Value({"years": y, "months": m, "days": d}, "duration",
                 _slice(lx, start))


def _struct(lx: _Lexer) -> Value:
    """`{ Name f = v; g = w; }`, or `{Name}` when the struct has no fields."""
    start = lx.i
    lx.expect("{")
    kind, name = lx.next()
    if kind != "ident":
        raise ParseError(f"struct without a name in {lx.text!r}")
    fields: dict = {}
    exact = True
    while lx.peek()[1] != "}":
        fkind, fname = lx.next()
        if fkind != "ident":
            raise ParseError(f"field name expected, found {fname!r} "
                             f"in {lx.text!r}")
        lx.expect("=")
        v = _value(lx)
        fields[fname] = v.py
        exact = exact and v.exact
        # The printer puts a `;` after every field, the last included; tolerate
        # its absence anyway.
        if lx.peek()[1] == ";":
            lx.next()
    lx.expect("}")
    return Value({"struct": name, "fields": fields}, "struct",
                 _slice(lx, start), exact)


def _paren(lx: _Lexer) -> Value:
    """`()` is unit, `(a, b)` a tuple, `(e)` a parenthesized value."""
    start = lx.i
    lx.expect("(")
    if lx.peek()[1] == ")":
        lx.next()
        return Value(None, "unit", "()")
    items = [_value(lx)]
    while lx.peek()[1] == ",":
        lx.next()
        items.append(_value(lx))
    lx.expect(")")
    if len(items) == 1:
        return items[0]
    return Value([v.py for v in items], "tuple", _slice(lx, start),
                 all(v.exact for v in items))


def _slice(lx: _Lexer, start: int) -> str:
    return " ".join(v for _, v in lx.toks[start:lx.i])
