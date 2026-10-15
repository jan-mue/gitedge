"""Backend syntax highlighting, token changes, and split-diff alignment."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from itertools import pairwise
from typing import TYPE_CHECKING

from dulwich.objects import S_ISGITLINK, Blob, Tree
from pygments.lexers import TextLexer, get_lexer_for_filename
from pygments.util import ClassNotFound

from app.schemas.repositories import DiffHunk, DiffLine, DiffRow, DiffToken

if TYPE_CHECKING:
    from dulwich.object_store import BaseObjectStore
    from dulwich.objects import ObjectID

    from app.schemas.repositories import CommitFileChange

HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
MAX_HIGHLIGHT_BYTES = 1_000_000
MAX_INLINE_TOKENS = 2000


def _source(store: BaseObjectStore, tree_id: ObjectID | None, path: str) -> str:
    """Read a text blob at a tree path, preserving newlines."""
    if tree_id is None:
        return ""
    tree = store[tree_id]
    if not isinstance(tree, Tree):
        return ""
    try:
        mode, oid = tree.lookup_path(store.__getitem__, path.encode())
    except KeyError:
        return ""
    if S_ISGITLINK(mode):
        return ""
    blob = store[oid]
    return blob.data.decode("utf-8", errors="replace") if isinstance(blob, Blob) else ""


def _syntax_lines(path: str, source: str, wanted: set[int]) -> tuple[str, dict[int, list[DiffToken]]]:
    """Preserve lexer context, retaining tokens only for lines displayed in the diff."""
    source = source.replace("\r\n", "\n")
    try:
        lexer = get_lexer_for_filename(path, stripnl=False, ensurenl=False)
    except ClassNotFound:
        lexer = TextLexer(stripnl=False, ensurenl=False)
    if len(source) > MAX_HIGHLIGHT_BYTES:
        lexer = TextLexer(stripnl=False, ensurenl=False)
    lines: dict[int, list[DiffToken]] = {number: [] for number in wanted}
    if not wanted:
        return lexer.name, lines
    number, last = 1, max(wanted)
    for _, token_type, value in lexer.get_tokens_unprocessed(source):
        if number > last:
            break
        syntax = str(token_type).removeprefix("Token.").lower().replace(".", "-")
        for index, part in enumerate(value.split("\n")):
            if index:
                number += 1
            if part and number in wanted:
                lines[number].append(DiffToken(text=part, syntax=syntax))
    return lexer.name, lines


def _words(line: DiffLine) -> list[str]:
    return re.findall(r"\w+|\s+|[^\w\s]", "".join(token.text for token in line.tokens))


def _emphasize(line: DiffLine, ranges: list[tuple[int, int]]) -> None:
    """Intersect changed token ranges with syntax tokens without emitting HTML."""
    tokens: list[DiffToken] = []
    offset = 0
    for token in line.tokens:
        end = offset + len(token.text)
        boundaries = sorted(
            {
                offset,
                end,
                *(max(offset, a) for a, b in ranges if a < end and b > offset),
                *(min(end, b) for a, b in ranges if a < end and b > offset),
            }
        )
        for start, stop in pairwise(boundaries):
            tokens.append(
                DiffToken(
                    text=token.text[start - offset : stop - offset],
                    syntax=token.syntax,
                    changed=any(a <= start < b for a, b in ranges),
                )
            )
        offset = end
    line.tokens = tokens


def _inline(old: DiffLine, new: DiffLine) -> None:
    before, after = _words(old), _words(new)
    if len(before) + len(after) > MAX_INLINE_TOKENS:
        return
    old_ranges: list[tuple[int, int]] = []
    new_ranges: list[tuple[int, int]] = []
    old_offsets = [0]
    new_offsets = [0]
    for word in before:
        old_offsets.append(old_offsets[-1] + len(word))
    for word in after:
        new_offsets.append(new_offsets[-1] + len(word))
    for kind, a, b, c, d in SequenceMatcher(None, before, after, autojunk=False).get_opcodes():
        if kind != "equal":
            old_ranges.append((old_offsets[a], old_offsets[b]))
            new_ranges.append((new_offsets[c], new_offsets[d]))
    _emphasize(old, old_ranges)
    _emphasize(new, new_ranges)


def _align(hunk: DiffHunk) -> None:
    """Pair each consecutive replacement block for split rendering and token diffs."""
    index = 0
    while index < len(hunk.lines):
        if hunk.lines[index].kind == "context":
            hunk.rows.append(DiffRow(old=index, new=index))
            index += 1
            continue
        removed: list[int] = []
        added: list[int] = []
        while index < len(hunk.lines) and hunk.lines[index].kind != "context":
            (removed if hunk.lines[index].kind == "delete" else added).append(index)
            index += 1
        for pair in range(max(len(removed), len(added))):
            old = removed[pair] if pair < len(removed) else None
            new = added[pair] if pair < len(added) else None
            hunk.rows.append(DiffRow(old=old, new=new))
            if old is not None and new is not None:
                _inline(hunk.lines[old], hunk.lines[new])


def enrich_diff(
    files: list[CommitFileChange], store: BaseObjectStore, old_tree: ObjectID | None, new_tree: ObjectID
) -> None:
    """Add syntax tokens, line numbers and split alignment to a parsed Git patch."""
    for file in files:
        file.is_binary = any(line.startswith("Binary files ") for line in file.patch.split("\n"))
        if file.is_binary:
            continue
        hunk: DiffHunk | None = None
        old_number = new_number = 0
        for raw in file.patch.split("\n"):
            match = HUNK_HEADER.match(raw)
            if match:
                hunk = DiffHunk(header=raw, lines=[], rows=[])
                file.hunks.append(hunk)
                old_number, new_number = int(match[1]), int(match[2])
            elif hunk is not None and raw.startswith("\\"):
                if hunk.lines:
                    hunk.lines[-1].no_newline = True
            elif hunk is not None and raw[:1] in (" ", "+", "-"):
                kind = {" ": "context", "+": "add", "-": "delete"}[raw[0]]
                hunk.lines.append(
                    DiffLine(
                        kind=kind,
                        old_line=old_number if kind != "add" else None,
                        new_line=new_number if kind != "delete" else None,
                        tokens=[DiffToken(text=raw[1:].removesuffix("\r"))],
                    )
                )
                old_number += kind != "add"
                new_number += kind != "delete"
        lines = [line for hunk in file.hunks for line in hunk.lines]
        _, old_tokens = _syntax_lines(
            file.old_path or file.path,
            _source(store, old_tree, file.old_path or file.path),
            {line.old_line for line in lines if line.kind == "delete" and line.old_line is not None},
        )
        file.language, new_tokens = _syntax_lines(
            file.path,
            _source(store, new_tree, file.path),
            {line.new_line for line in lines if line.kind != "delete" and line.new_line is not None},
        )
        for line in lines:
            tokens = old_tokens.get(line.old_line or 0) if line.kind == "delete" else new_tokens.get(line.new_line or 0)
            if tokens:
                line.tokens = tokens
        for hunk in file.hunks:
            _align(hunk)
        file.additions = sum(line.kind == "add" for hunk in file.hunks for line in hunk.lines)
        file.deletions = sum(line.kind == "delete" for hunk in file.hunks for line in hunk.lines)
