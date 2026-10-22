"""Mask quality: how much of the vocab does the mask keep, by grammar state?

The honest metric for a constrained decoder isn't just correctness — it's
*selectivity* (how many candidates it prunes) and *availability* (does any
token survive, or did the mask deadlock the model?). A mask that is sound
but starves the model of tokens at high-probability positions is a
generation-killer: the demo computes exactly that curve.
"""

import sys

import pytest

sys.path.insert(0, ".")
from pushdown import JsonPDA  # noqa: E402
from pushdown.masking import build_mask, first_divergent, vocab_tokens  # noqa: E402


def test_selectivity_curve():
    """At mid-object the mask keeps mostly string content; at structural
    positions it is brutal. Both extremes: no-zero-survivors (deadlock) is a bug."""
    toks = vocab_tokens()
    states = ['{"a":', '{"a":[', '{"a":[1,', '{"a":{"b"', '{"a":[1,2]}']
    keep = []
    for s in states:
        mask, _ = build_mask(s, toks)
        keep.append(sum(mask))
    assert all(k > 0 for k in keep), f"mask deadlocked a valid state: {list(zip(states, keep))}"


def test_bad_prefix_deadlocks_legitimately():
    """Prefix that cannot be completed: every token must be masked out."""
    toks = vocab_tokens()
    mask, _ = build_mask('{"a":}}}', toks)
    assert not any(mask)


def test_first_divergent():
    toks = vocab_tokens()
    assert first_divergent('{"a":', toks) is not None
    assert first_divergent('{"a":}}}', toks) is None


def test_allowed_chars_are_survivable():
    """Liveness check for the mask hook: every char `allowed_chars()` offers
    must actually survive `feed()` from the same state."""
    prefixes = ['{"a":', '{"a":[1', "[", "[[", '{"b"', '{"a":{"c"', '"abc', '{"a":1,']
    for pfx in prefixes:
        pda = JsonPDA()
        pda.accepts(pfx)
        if pda.st.mode == "DEAD":
            pytest.fail(f"prefix replay died: {pfx!r}")
        ok, _ = pda.allowed_chars()
        for ch in ok:
            probe = JsonPDA()
            probe.restore(pda.snapshot())
            assert probe.feed(ch), f"{pfx!r} + {ch!r} rejected despite allowed_chars"
