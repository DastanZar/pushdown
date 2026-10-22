"""Reproducible CPU measurement; run from any directory."""

import hashlib
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def metadata():
    files = sorted((ROOT / ROOT.name).glob("*.py"))
    digest = hashlib.sha256(b"".join(p.read_bytes() for p in files)).hexdigest()
    return {
        "utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "source_sha256": digest,
        "clock": "perf_counter_ns",
        "warmup": 2,
        "repeats": 7,
    }


def timed(fn):
    for _ in range(2):
        fn()
    samples = []
    for _ in range(7):
        start = time.perf_counter_ns()
        fn()
        samples.append((time.perf_counter_ns() - start) / 1000)
    return {
        "samples_us": samples,
        "median_us": median(samples),
        "min_us": min(samples),
        "max_us": max(samples),
    }


def save(receipt):
    (ROOT / "receipts").mkdir(exist_ok=True)
    (ROOT / "receipts" / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    print("BENCHMARK_OK")


from pushdown import JsonPDA, build_mask, vocab_tokens  # noqa: E402
from pushdown.baseline import BoundedStackMasker  # noqa: E402


def main():
    depths = []
    for depth in [1, 3, 4, 8, 32, 128, 512, 1024]:
        doc = "[" * depth + "1" + "]" * depth
        accepted = JsonPDA().accepts(doc)
        assert accepted
        bounded = BoundedStackMasker(3).accepts(doc)
        assert bounded == (depth <= 3)
        row = {
            "depth": depth,
            "chars": len(doc),
            "pda_accepts": accepted,
            "synthetic_cap3_accepts": bounded,
            "pda": timed(lambda: JsonPDA().accepts(doc)),
        }
        if depth <= 512:
            assert json.loads(doc) is not None
            row["stdlib"] = timed(lambda: json.loads(doc))
        depths.append(row)
    selectivity = []
    tokens = vocab_tokens()
    for label, prefix in [
        ("value", '{"a":'),
        ("number-zero", "0"),
        ("string", '"ab'),
        ("key", '{"a":1,'),
        ("done", "{}"),
    ]:
        mask, pda = build_mask(prefix, tokens)
        selectivity.append(
            {
                "state": label,
                "prefix": prefix,
                "kept": sum(mask),
                "vocab_size": len(tokens),
                "eos_legal": pda.final_ok(),
                "mask_with_replay": timed(lambda: build_mask(prefix, tokens)),
            }
        )
    doc = '{"a":[{"b":[1,2]},3]}'
    parser = JsonPDA()
    trace = []
    for i, char in enumerate(doc):
        assert parser.feed(char)
        trace.append(
            {
                "step": i + 1,
                "char": char,
                "mode": parser.st.mode,
                "stack": [frame.kind for frame in parser.st.stack],
            }
        )
    save(
        {
            "metadata": metadata(),
            "scope": "synthetic capped stack, NOT production DFA comparison",
            "depth_scaling": depths,
            "selectivity": selectivity,
            "trace": trace,
            "semantic_mask_integration": False,
        }
    )


if __name__ == "__main__":
    main()
