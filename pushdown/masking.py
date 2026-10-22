"""Syntax-only masking over context-independent Unicode token renderings."""

from __future__ import annotations

from collections.abc import Iterable

from .pda import JsonPDA


def vocab_tokens(vocab: Iterable[str] | None = None) -> list[str]:
    """Use the supplied renderings, or a deliberately small demonstration vocabulary."""
    if vocab is not None:
        return list(vocab)
    return [chr(c) for c in range(0x20, 0x7F)] + [
        "\n",
        "  ",
        "1.5",
        "true",
        "null",
        '"],[',
        "}{",
        ' "',
    ]


def mask_step(pda: JsonPDA, tokens: list[str], eos_legal: bool = False) -> list[bool]:
    """Probe each rendering without mutating caller state or completion events.

    eos_legal=True asks if EOS is legal after each candidate, not just whether
    the rendering is a viable prefix. Empty renderings are rejected.
    """
    out = []
    for token in tokens:
        probe = JsonPDA()
        probe.restore(pda.snapshot())
        ok = bool(token) and all(probe.feed(ch) for ch in token)
        out.append(ok and (not eos_legal or probe.final_ok()))
    return out


def build_mask(prefix_text: str, tokens: list[str]) -> tuple[list[bool], JsonPDA]:
    """Replay without finalizing: a numeric prefix can still grow."""
    pda = JsonPDA()
    for ch in prefix_text:
        if not pda.feed(ch):
            break
    return mask_step(pda, tokens), pda


def first_divergent(prefix: str, tokens: list[str]) -> str | None:
    """Legacy name: returns the first ALLOWED token, or None."""
    mask, _ = build_mask(prefix, tokens)
    return next((token for token, allowed in zip(tokens, mask) if allowed), None)
