"""Synthetic capped-stack baseline: deliberately not a production DFA."""

from .pda import JsonPDA


class BoundedStackMasker:
    def __init__(self, L: int = 3) -> None:
        self.L = L

    def accepts(self, text: str) -> bool:
        parser = JsonPDA()
        for ch in text:
            if not parser.feed(ch) or len(parser.st.stack) > self.L:
                return False
        return parser.finish()
