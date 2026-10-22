"""JSON differential checks and a deliberately synthetic stack cap."""

import json
import random
import sys

import pytest

sys.path.insert(0, ".")
from pushdown import JsonPDA  # noqa: E402
from pushdown.baseline import BoundedStackMasker  # noqa: E402


CORPUS = [
    "1",
    "-1.5e3",
    '"s"',
    "true",
    "false",
    "null",
    "[]",
    "{}",
    "[[]]",
    '{"a":1}',
    '{"a":[1,2,{"b":null}]}',
    "[[[[[[[[[[1]]]]]]]]]]",
    '{"a": {"b": {"c": {"d": [1]}}}}',
    '"\\u00e9x"',
    '["a","b"]',
    ' {"x" : [ 1 , 2 ] } ',
    "[1,2,]",
    '{"a":}',
    "{,}",
    "[1,,2]",
    '"abc',
    "01",
    "-",
    "+1",
    "1.",
    "tru",
    '{"a" 1}',
    "{'a':1}",
    "[1 2]",
    "{}]",
    "[}",
]


def ref_valid(s: str) -> bool:
    try:
        json.loads(s)
        return True
    except Exception:
        return False


@pytest.mark.parametrize("doc", CORPUS)
def test_pda_agrees_with_json(doc):
    assert JsonPDA().accepts(doc) == ref_valid(doc), doc


def test_deep_valid_documents():
    for depth in (2, 8, 32, 64):
        deep = "[" * depth + "1" + "]" * depth
        assert JsonPDA().accepts(deep)
        assert not JsonPDA().accepts(deep + "]")
        assert not JsonPDA().accepts(deep[:-1])


# --------------------------------------------------- the bounded-stack cliff


def test_bounded_masker_is_incomplete_past_its_depth():
    """A valid depth-4 document: bounded masker rejects, PDA accepts."""
    valid = json.dumps([[[[1]]]])
    assert ref_valid(valid)
    assert BoundedStackMasker(L=3).accepts(valid) is False
    assert JsonPDA().accepts(valid) is True


def test_bounded_masker_agrees_under_its_depth():
    """Soundness is preserved: at cap >= corpus depth it matches json.loads."""
    b = BoundedStackMasker(L=12)
    for doc in CORPUS:
        assert b.accepts(doc) == ref_valid(doc), doc


def test_masking_step_eos_legality():
    from pushdown import build_mask, vocab_tokens

    toks = vocab_tokens()
    _, mid = build_mask('{"a":', toks)
    assert mid.allowed_chars()[1] is False  # document incomplete: EOS illegal
    _, done = build_mask('{"a":1}', toks)
    assert done.allowed_chars()[1] is True  # complete: EOS legal


def test_semantic_layer_removes_and_never_adds():
    """A separate scalar-side-memory query; NOT integrated token enforcement."""
    from pushdown import Rule, SideMemory

    mem = SideMemory(rules=[Rule(path=("tags",), kind="unique")])
    pda = JsonPDA()
    assert pda.accepts('{"tags": ["a", "b"]}')
    items = [v for (p, v) in pda.drain_events() if len(p) == 2 and p[0] == "tags"]
    assert items == ["a", "b"]
    for i, v in enumerate(items):
        mem.observe(("tags", i), v)
    assert pda.accepts('{"tags": ["a", "b", "a"]}')  # structural layer: legal
    assert mem.denies(("tags", 2), "a")  # semantic layer: denied
    assert not mem.denies(("tags", 2), "c")  # and adds nothing


def test_random_documents_agree_with_json():
    rng = random.Random(7)

    def gen(depth=0):
        r = rng.random()
        if depth < 3 and r < 0.25:
            return [gen(depth + 1) for _ in range(rng.randint(0, 3))]
        if depth < 3 and r < 0.45:
            return {f"k{i}": gen(depth + 1) for i in range(rng.randint(0, 3))}
        return rng.choice([1, -2.5, "str", True, False, None, "e\\sc"])

    docs = [json.dumps(gen()) for _ in range(150)]
    mutated = [d[: len(d) // 2] + rng.choice('{}[],"0: ') + d[len(d) // 2 :] for d in docs[:75]]
    for d in docs + mutated:
        assert JsonPDA().accepts(d) == ref_valid(d), repr(d)
