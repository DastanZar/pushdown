import itertools
import json
import random
import re

from pushdown import JsonPDA, build_mask, mask_step
from pushdown.baseline import BoundedStackMasker


def valid(text):
    try:
        json.loads(text, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        return True
    except ValueError:
        return False


def test_numeric_prefix_masks_against_independent_regex():
    pattern = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z")
    suffixes = ("", "0", "1", "e0", ".0", "0e0")
    for length in range(1, 5):
        for chars in itertools.product("01.e+-", repeat=length):
            prefix = "".join(chars)
            viable = any(pattern.fullmatch(prefix + suffix) for suffix in suffixes)
            mask, parser = build_mask(prefix, ["0", "e", ".", "1", "-", "+"])
            assert (parser.st.mode != "DEAD") == viable, prefix
            for token, allowed in zip(["0", "e", ".", "1", "-", "+"], mask):
                expected = any(pattern.fullmatch(prefix + token + suffix) for suffix in suffixes)
                assert allowed == bool(expected), (prefix, token)


def test_random_syntax_mutations_and_final_masks():
    rng = random.Random(51)
    tokens = ["}", "]", '"', "true", ":", "0", " ", "e+", "\\u00", "\n", "💀"]
    values = [None, True, False, 1, -0.03, "\n\té💀", [], {}, [1, 2]]
    for _ in range(600):
        doc = json.dumps({"é": rng.choices(values, k=4)}, ensure_ascii=rng.choice([True, False]))
        cut = rng.randrange(len(doc) + 1)
        mutated = doc[:cut] + rng.choice(tokens) + doc[cut:]
        assert JsonPDA().accepts(mutated) == valid(mutated)
        _, parser = build_mask(doc[:cut], tokens)
        for token, allowed in zip(tokens, mask_step(parser, tokens, eos_legal=True)):
            assert allowed == valid(doc[:cut] + token)


def test_bounded_baseline_ignores_brackets_in_strings():
    assert BoundedStackMasker(1).accepts('["[[[{{{"]')
