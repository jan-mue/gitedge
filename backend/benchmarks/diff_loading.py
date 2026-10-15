"""Reproducible CPU-only diff-loading fixtures; run from backend with PYTHONPATH=."""

import statistics
import time

from dulwich.object_store import MemoryObjectStore
from dulwich.objects import Blob, Tree

from app.services.repositories import RepositoryService

CHANGED_LINE = 120


def measure_index(*, repeated: bool) -> None:
    """Measure 500 changed files with forty lines on each side."""
    store = MemoryObjectStore()
    trees = [Tree(), Tree()]
    for file in range(500):
        for version, tree in enumerate(trees):
            content = "".join(
                f"export const file_{0 if repeated else file}_value_{line} = {12 if version == 0 else 42}; // configuration\n"
                for line in range(40)
            ).encode()
            blob = Blob.from_string(content)
            store.add_object(blob)
            tree.add(f"file-{file:04}.ts".encode(), 0o100644, blob.id)
    for tree in trees:
        store.add_object(tree)
    timings = []
    for _ in range(7):
        start = time.perf_counter()
        RepositoryService._diff_files(store, trees[0].id, trees[1].id, False)  # noqa: SLF001
        timings.append((time.perf_counter() - start) * 1000)
    print(
        {
            "scenario": "repeated" if repeated else "unique",
            "files": 500,
            "median_ms": round(statistics.median(timings), 2),
        }
    )


def measure_sparse_change() -> None:
    """Measure one hunk near the beginning of a 20,000-line file."""
    store = MemoryObjectStore()
    trees = []
    for version in range(2):
        content = "".join(
            f"value_{line} = {42 if line == CHANGED_LINE and version else 12}\n" for line in range(20000)
        ).encode()
        blob = Blob.from_string(content)
        store.add_object(blob)
        tree = Tree()
        tree.add(b"large.py", 0o100644, blob.id)
        store.add_object(tree)
        trees.append(tree)
    timings = []
    for _ in range(5):
        start = time.perf_counter()
        file = RepositoryService._diff_file(store, trees[0].id, trees[1].id, "large.py")  # noqa: SLF001
        timings.append((time.perf_counter() - start) * 1000)
    print(
        {
            "scenario": "20000-lines-one-hunk",
            "median_ms": round(statistics.median(timings), 2),
            "payload_bytes": len(file.model_dump_json()),
        }
    )


if __name__ == "__main__":
    measure_index(repeated=False)
    measure_index(repeated=True)
    measure_sparse_change()
