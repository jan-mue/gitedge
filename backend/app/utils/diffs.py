"""Engine-independent review comment context."""

from typing import Literal

from app.schemas.repositories import DiffHunk, DiffToken


def comment_context(hunks: list[DiffHunk], side: Literal["old", "new"], number: int) -> DiffHunk | None:
    """Return up to four existing diff lines, ending exactly at the comment anchor."""
    for hunk in hunks:
        for index, line in enumerate(hunk.lines):
            if (line.old_line if side == "old" else line.new_line) == number:
                lines = [line.model_copy(deep=True) for line in hunk.lines[max(0, index - 3) : index + 1]]
                for context_line in lines:
                    remaining = 2048
                    tokens = []
                    for token in context_line.tokens:
                        tokens.append(token.model_copy(update={"text": token.text[:remaining]}))
                        remaining -= len(token.text)
                        if remaining <= 0:
                            tokens.append(DiffToken(text=" …"))
                            break
                    context_line.tokens = tokens
                return DiffHunk(header=hunk.header, lines=lines, rows=[])
    return None
