"""Syntax-only JSON prefix masks with an explicit stack.

SideMemory is a separate experimental scalar-event helper, not integrated
with mask_step and not a JSON Schema validator. Prior-art context: XGrammar
and Outlines; no production implementation is benchmarked here."""

from .masking import build_mask, first_divergent, mask_step, vocab_tokens
from .pda import Frame, JsonPDA, State
from .semantic import Rule, SideMemory, guide_allows

__all__ = [
    "JsonPDA",
    "Frame",
    "State",
    "SideMemory",
    "Rule",
    "guide_allows",
    "build_mask",
    "mask_step",
    "first_divergent",
    "vocab_tokens",
]
