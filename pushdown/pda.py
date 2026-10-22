"""Pushdown automaton for the JSON grammar — a character machine with an
explicit stack, built to be masked against and cross-checked by `json`.

The explicit stack has no configured depth cap. Benchmarks compare only a
synthetic capped version of this recognizer, NOT a production decoder.
XGrammar is not a bounded DFA. This Python implementation makes no
production performance claim.

Modes: VALUE | KEY | COLON | SEP | STR | NUM | LIT | DONE | DEAD.

Conventions:
  * A `Frame` is the *open container* on top of the stack; `key`/`index`
    point at the slot currently being filled. `nonempty` distinguishes a
    container that has never held a value (close is legal) from one whose
    last element ended in a comma (close is a syntax error).
  * A completion event carries `path = tuple(slot of each open frame)` — the
    JSON pointer of the value that just finished.
  * Number termination re-dispatches the terminating character. A lexical
    state machine rejects numeric prefixes that cannot be completed.
"""

from __future__ import annotations

import json
import string
from dataclasses import dataclass, replace
from typing import List, Optional, Tuple

_ESCAPES = set('"\\/bfnrt')
_HEX = set("0123456789abcdefABCDEF")


@dataclass(frozen=True)
class Frame:
    kind: str  # "obj" | "arr"
    key: Optional[str] = None  # objects: key of the slot being filled
    index: int = 0  # arrays: index of the slot being filled
    nonempty: bool = False  # a value has ever landed in this container


@dataclass(frozen=True)
class State:
    stack: Tuple[Frame, ...] = ()
    mode: str = "VALUE"
    sbuf: str = ""
    str_role: str = "value"  # "key" | "value", only meaningful inside STR
    esc: bool = False
    num_mode: str = ""
    hex_left: int = 0  # remaining hex digits of a \uXXXX escape


def _lit_value(s: str) -> object:
    return {"true": True, "false": False, "null": None}[s]


class JsonPDA:
    """Incremental, stack-complete JSON recognizer with event emission."""

    def __init__(self) -> None:
        self.st = State()
        self.events: List[Tuple[tuple, object]] = []

    # ----------------------------------------------------------- public
    def accepts(self, s: str) -> bool:
        self.st = State()
        self.events = []
        for ch in s:
            if not self.feed(ch):
                return False
        return self.finish()

    def feed(self, ch: str) -> bool:
        if len(ch) != 1:
            raise ValueError("feed expects one Unicode character")
        st = self.st
        if st.mode == "DEAD":
            return False
        if st.mode == "DONE":
            return True if ch in " \t\r\n" else self._dead()
        if st.mode == "STR":
            return self._str(ch)
        if st.mode == "NUM":
            transitions = {
                "sign": {"zero": "zero", "digit": "int"},
                "zero": {".": "dot", "e": "exp"},
                "int": {"zero": "int", "digit": "int", ".": "dot", "e": "exp"},
                "dot": {"zero": "frac", "digit": "frac"},
                "frac": {"zero": "frac", "digit": "frac", "e": "exp"},
                "exp": {"+": "exp_sign", "-": "exp_sign", "zero": "exp_int", "digit": "exp_int"},
                "exp_sign": {"zero": "exp_int", "digit": "exp_int"},
                "exp_int": {"zero": "exp_int", "digit": "exp_int"},
            }
            key = (
                "zero" if ch == "0" else "digit" if ch in "123456789" else "e" if ch in "eE" else ch
            )
            nxt = transitions[st.num_mode].get(key)
            if nxt is not None:
                self.st = replace(st, sbuf=st.sbuf + ch, num_mode=nxt)
                return True
            if st.num_mode not in {"zero", "int", "frac", "exp_int"}:
                return self._dead()
            try:
                val = json.loads(st.sbuf)
            except Exception:
                return self._dead()
            self._complete(val)
            return self.feed(ch)  # the terminating char belongs to SEP/whitespace
        if st.mode == "LIT":
            return self._lit(ch)
        if ch in " \t\n\r":
            return True
        if st.mode == "VALUE":
            return self._value(ch)
        if st.mode == "KEY":
            if ch == '"':
                self.st = replace(st, mode="STR", sbuf="", str_role="key", esc=False)
                return True
            if ch == "}":
                if not st.stack[-1].nonempty:  # `{}` — empty objects close
                    self._close()
                    return True
            return self._dead()
        if st.mode == "COLON":
            if ch == ":":
                self.st = replace(st, mode="VALUE")
                return True
            return self._dead()
        if st.mode == "SEP":
            return self._sep(ch)
        return self._dead()

    def final_ok(self) -> bool:
        """Is end-of-sequence legal *right now*? (Pure lookahead: a trailing
        NUM/LIT buffer may terminate the document — `123` is valid JSON even
        though the scanner is mid-number.)"""
        st = self.st
        if st.mode == "DONE":
            return True
        if st.mode == "NUM":
            return st.num_mode in {"zero", "int", "frac", "exp_int"} and not st.stack
        if st.mode == "LIT":
            return st.sbuf in ("true", "false", "null") and not st.stack
        return False

    def finish(self) -> bool:
        """Terminate a trailing NUM/LIT buffer if present, then check DONE."""
        st = self.st
        if st.mode == "NUM":
            try:
                self._complete(json.loads(st.sbuf))
            except Exception:
                self._dead()
        elif st.mode == "LIT":
            if st.sbuf in ("true", "false", "null"):
                self._complete(_lit_value(st.sbuf))
            else:
                self._dead()
        return self.st.mode == "DONE"

    def snapshot(self) -> State:
        return self.st

    def restore(self, st: State) -> None:
        self.st = st

    def drain_events(self) -> List[Tuple[tuple, object]]:
        out, self.events = self.events, []
        return out

    # -------------------------------------- character legality (mask hook)
    def allowed_chars(self, alphabet: str = string.printable) -> Tuple[frozenset[str], bool]:
        """Exact viable next characters within a finite alphabet (ASCII by default).

        Unicode string content is supported by feed; pass it in alphabet to query.
        """
        allowed = set()
        for ch in alphabet:
            probe = JsonPDA()
            probe.restore(self.st)
            if probe.feed(ch):
                allowed.add(ch)
        return frozenset(allowed), self.final_ok()

    # -------------------------------------------------------- internals
    def _dead(self) -> bool:
        self.st = replace(self.st, mode="DEAD")
        return False

    def _value(self, ch: str) -> bool:
        st = self.st
        if ch == "{":
            self.st = replace(st, stack=st.stack + (Frame("obj"),), mode="KEY")
            return True
        if ch == "[":
            self.st = replace(st, stack=st.stack + (Frame("arr"),), mode="VALUE")
            return True
        if ch == '"':
            self.st = replace(st, mode="STR", sbuf="", str_role="value", esc=False)
            return True
        if ch in "0123456789-":
            num_mode = "sign" if ch == "-" else "zero" if ch == "0" else "int"
            self.st = replace(st, mode="NUM", sbuf=ch, num_mode=num_mode)
            return True
        if ch in "tfn":
            self.st = replace(st, mode="LIT", sbuf=ch)
            return True
        if ch == "]" and st.stack and st.stack[-1].kind == "arr" and not st.stack[-1].nonempty:
            self._close()  # `[]`
            return True
        return self._dead()

    def _str(self, ch: str) -> bool:
        st = self.st
        if st.hex_left:
            if ch not in _HEX:
                return self._dead()
            self.st = replace(st, sbuf=st.sbuf + ch, hex_left=st.hex_left - 1)
            return True
        if st.esc:
            if ch in _ESCAPES:
                self.st = replace(st, esc=False, sbuf=st.sbuf + ch)
                return True
            if ch == "u":
                self.st = replace(st, esc=False, hex_left=4, sbuf=st.sbuf + ch)
                return True
            return self._dead()
        if ch == "\\":
            self.st = replace(st, esc=True, sbuf=st.sbuf + ch)
            return True
        if ch == '"':
            content = json.loads('"' + st.sbuf + '"')
            if st.str_role == "key":
                fr = st.stack[-1]
                nf = replace(fr, key=content)
                self.st = replace(st, stack=st.stack[:-1] + (nf,), mode="COLON", sbuf="", esc=False)
                return True
            self._complete(content)
            return True
        if ord(ch) < 0x20:
            return self._dead()
        self.st = replace(st, sbuf=st.sbuf + ch)
        return True

    def _lit(self, ch: str) -> bool:
        st = self.st
        cands = [lit for lit in ("true", "false", "null") if lit.startswith(st.sbuf)]
        full = st.sbuf + ch
        if not any(lit.startswith(full) for lit in cands):
            return self._dead()
        if full in ("true", "false", "null"):
            self._complete(_lit_value(full))
            return True
        self.st = replace(st, sbuf=full)
        return True

    def _sep(self, ch: str) -> bool:
        st = self.st
        fr = st.stack[-1]
        if ch == ",":
            if fr.kind == "obj":
                self.st = replace(st, stack=st.stack[:-1] + (replace(fr, key=None),), mode="KEY")
            else:
                self.st = replace(
                    st, stack=st.stack[:-1] + (replace(fr, index=fr.index + 1),), mode="VALUE"
                )
            return True
        if (ch == "}" and fr.kind == "obj") or (ch == "]" and fr.kind == "arr"):
            self._close()
            return True
        return self._dead()

    def _close(self) -> None:
        """`}`/`]` arrived: pop the closed container, then record ITS
        completion inside the parent frame."""
        st = self.st
        kind = st.stack[-1].kind
        self.st = replace(st, stack=st.stack[:-1])
        self._complete(f"<{kind}>")

    def _complete(self, value: object) -> None:
        """A value (scalar or closed container) landed in the top frame's slot."""
        st = self.st
        if st.stack:
            fr = st.stack[-1]
            path = tuple(f.key if f.kind == "obj" else f.index for f in st.stack)
            nf = replace(fr, nonempty=True)
            self.events.append((path, value))
            self.st = replace(st, stack=st.stack[:-1] + (nf,), mode="SEP", sbuf="")
        else:
            self.events.append(((), value))
            self.st = replace(st, mode="DONE", sbuf="")
