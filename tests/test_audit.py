import json

import pytest

from pushdown import JsonPDA, build_mask, mask_step


@pytest.mark.parametrize("doc", ["\v1", "1\u00a0", "[1\f]", "[١]", "{}x"])
def test_strict_json_whitespace_and_digits(doc):
    with pytest.raises(ValueError):
        json.loads(doc)
    assert not JsonPDA().accepts(doc)


def test_mask_is_viable_and_observationally_pure():
    tokens = ["1", ".", "e", "-", "+", "0", " ", "}"]
    mask, pda = build_mask("0", tokens)
    assert mask == [False, True, True, False, False, False, True, False]
    state, events = pda.snapshot(), list(pda.events)
    mask_step(pda, tokens)
    assert pda.snapshot() == state and pda.events == events


def test_escaped_event_values_match_stdlib():
    doc = r'{"\u0061": ["\n", "\u00e9", "\ud83d\udc80"]}'
    pda = JsonPDA()
    assert pda.accepts(doc)
    assert [v for p, v in pda.events if len(p) == 2] == json.loads(doc)["a"]


def test_capture_none_is_not_missing_and_counts_are_scoped():
    from pushdown import Rule, SideMemory

    mem = SideMemory([Rule(("a",), "capture", name="v"), Rule(("b",), "equals_capture", name="v")])
    mem.observe(("a",), None)
    assert mem.denies(("b",), 1)
    assert not mem.denies(("b",), None)
