"""Verify server-generated highlighting, token changes and diff alignment."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, Literal

import pytest
from dulwich.object_store import MemoryObjectStore
from dulwich.objects import Blob, ObjectID, Tree
from dulwich.patch import write_tree_diff

from app.clients.git.diffs import enrich_diff
from app.clients.git.repositories import GitClient
from app.utils.diffs import comment_context

if TYPE_CHECKING:
    from app.schemas.repositories import CommitFileChange


def make_diff(before: bytes | None, after: bytes | None, path: str = "example.py") -> list[CommitFileChange]:
    store = MemoryObjectStore()
    trees = []
    for source in (before, after):
        tree = Tree()
        if source is not None:
            blob = Blob.from_string(source)
            store.add_object(blob)
            tree.add(path.encode(), 0o100644, blob.id)
        store.add_object(tree)
        trees.append(tree)
    patch = io.BytesIO()
    write_tree_diff(patch, store, trees[0].id, trees[1].id)
    files = GitClient._parse_patch(patch.getvalue().decode())  # noqa: SLF001
    enrich_diff(files, store, trees[0].id, trees[1].id)
    return files


def test_only_changed_tokens_are_emphasized_and_split_rows_are_aligned() -> None:
    file = make_diff(b"count = 12\nprint(count)\n", b"count = 42\nprint(count)\n")[0]
    old, new, context = file.hunks[0].lines
    assert (old.old_line, old.new_line, new.old_line, new.new_line) == (1, None, None, 1)
    assert [(token.text, token.syntax) for token in new.tokens if token.changed] == [("42", "literal-number-integer")]
    assert [token.text for token in old.tokens if token.changed] == ["12"]
    assert not any(token.changed for token in context.tokens)
    assert [row.model_dump() for row in file.hunks[0].rows] == [{"old": 0, "new": 1}, {"old": 2, "new": 2}]
    assert (file.additions, file.deletions, file.language) == (1, 1, "Python")


@pytest.mark.parametrize("side", ["old", "new"])
def test_compact_context_ends_at_anchor_and_preserves_token_changes(side: Literal["old", "new"]) -> None:
    store = MemoryObjectStore()
    trees = []
    for value in (12, 42):
        blob = Blob.from_string(f"value = {value}\nprint(value)\n".encode())
        store.add_object(blob)
        tree = Tree()
        tree.add(b"code.py", 0o100644, blob.id)
        store.add_object(tree)
        trees.append(tree)
    file = GitClient._diff_file(store, trees[0].id, trees[1].id, "code.py", (side, 1))  # noqa: SLF001
    lines = file.hunks[0].lines
    assert (lines[-1].old_line if side == "old" else lines[-1].new_line) == 1
    assert len(lines) <= 4
    assert any(token.changed for token in lines[-1].tokens)
    assert all("print" not in token.text for line in lines for token in line.tokens)


def test_context_snapshots_bound_long_lines_without_mutating_the_full_diff() -> None:
    file = make_diff(b"x = 1\n", b"x = '" + b"a" * 5000 + b"'\n")[0]
    context = comment_context(file.hunks, "new", 1)
    assert context is not None
    assert len("".join(token.text for token in context.lines[-1].tokens)) <= 2050
    assert len("".join(token.text for token in file.hunks[0].lines[-1].tokens)) > 5000


def test_multiline_syntax_is_lexed_from_whole_blob_outside_hunk() -> None:
    before = b'"""\n' + b"text\n" * 8 + b"old\n" + b"text\n" * 8 + b'"""\n'
    file = make_diff(before, before.replace(b"old\n", b"new\n"))[0]
    number = file.hunks[0].lines[0].old_line
    assert number is not None
    assert number > 1
    changed = next(line for line in file.hunks[0].lines if line.kind == "add")
    assert all(token.syntax.startswith("literal-string") for token in changed.tokens)


@pytest.mark.parametrize(("before", "after", "kind"), [(None, b"hello\n", "add"), (b"hello\n", None, "delete")])
def test_added_and_deleted_files_have_correct_line_numbers(
    before: bytes | None, after: bytes | None, kind: str
) -> None:
    file = make_diff(before, after)[0]
    line = file.hunks[0].lines[0]
    assert line.kind == kind
    assert (line.old_line, line.new_line) == ((1, None) if kind == "delete" else (None, 1))


def test_patch_like_content_and_no_newline_are_preserved() -> None:
    file = make_diff(b"-- old", b"++ new", "unknown-extension.xyz")[0]
    assert (file.additions, file.deletions) == (1, 1)
    assert all(line.no_newline for line in file.hunks[0].lines)
    assert "".join(token.text for token in file.hunks[0].lines[1].tokens) == "++ new"


def test_binary_files_have_no_text_hunks() -> None:
    file = make_diff(b"\x00before", b"\x00after", "image.bin")[0]
    assert file.is_binary
    assert file.hunks == []


def test_unequal_replacement_block_preserves_every_line() -> None:
    file = make_diff(b"one\ntwo\n", b"three\n", "file.txt")[0]
    assert [(row.old, row.new) for row in file.hunks[0].rows] == [(0, 2), (1, None)]
    assert (file.additions, file.deletions) == (1, 2)


def test_crlf_tokens_do_not_add_extra_visual_lines() -> None:
    file = make_diff(b"count = 12\r\n", b"count = 42\r\n")[0]
    assert len(file.hunks[0].lines) == 2
    assert not any("\r" in token.text for line in file.hunks[0].lines for token in line.tokens)


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (None, b"new file\n"),
        (b"deleted\n", None),
        (b"a\r\nb\r\n", b"a\r\nc\r\n"),
        (b"\0old", b"\0new"),
        (b"old", b"new"),
        (b"one\n" * 300, b"two\n" * 300),
        (b"context\n" * 8 + b"old\n" + b"context\n" * 8, b"context\n" * 8 + b"new\n" + b"context\n" * 8),
    ],
)
def test_compact_index_statistics_match_highlighted_patch(before: bytes | None, after: bytes | None) -> None:
    store = MemoryObjectStore()
    trees = []
    for source in (before, after):
        tree = Tree()
        if source is not None:
            blob = Blob.from_string(source)
            store.add_object(blob)
            tree.add(b"example.py", 0o100644, blob.id)
        store.add_object(tree)
        trees.append(tree)
    summary = GitClient._diff_files(store, trees[0].id, trees[1].id, False)[0]  # noqa: SLF001
    full = GitClient._diff_files(store, trees[0].id, trees[1].id, True)[0]  # noqa: SLF001
    fields = {"path", "change_type", "additions", "deletions", "diff_line_count", "is_binary"}
    assert summary.model_dump(include=fields) == full.model_dump(include=fields)
    assert not summary.patch
    assert not summary.hunks
    assert not summary.diff_loaded


def test_submodule_commit_does_not_need_to_exist_in_parent_object_store() -> None:
    store = MemoryObjectStore()
    old, new = Tree(), Tree()
    old.add(b"dependency", 0o160000, ObjectID(b"a" * 40))
    new.add(b"dependency", 0o160000, ObjectID(b"b" * 40))
    store.add_object(old)
    store.add_object(new)
    patch = io.BytesIO()
    write_tree_diff(patch, store, old.id, new.id)
    files = GitClient._parse_patch(patch.getvalue().decode())  # noqa: SLF001
    enrich_diff(files, store, old.id, new.id)
    assert files[0].hunks
    assert "Subproject commit" in files[0].patch
