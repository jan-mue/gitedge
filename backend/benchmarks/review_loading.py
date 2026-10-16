"""Compare full-file review loading with bounded context; run with PYTHONPATH=."""

import statistics
import time

from dulwich.object_store import MemoryObjectStore
from dulwich.objects import Blob, Tree

from app.services.repositories import RepositoryService


def measure() -> None:
    """Compare CPU time and serialized bytes on the same 10,000-row diff."""
    store = MemoryObjectStore()
    trees = []
    for version in range(2):
        blob = Blob.from_string(
            "".join(f"value_{line} = {12 if version == 0 else 42}\n" for line in range(5000)).encode()
        )
        store.add_object(blob)
        tree = Tree()
        tree.add(b"large.py", 0o100644, blob.id)
        store.add_object(tree)
        trees.append(tree)
    for anchor in (None, ("old", 1), ("new", 1)):
        timings = []
        for _ in range(3):
            start = time.perf_counter()
            file = RepositoryService._diff_file(store, trees[0].id, trees[1].id, "large.py", anchor)  # noqa: SLF001
            timings.append((time.perf_counter() - start) * 1000)
        payload = file.model_dump_json() if anchor is None else file.hunks[0].model_dump_json()
        print(
            {
                "anchor": anchor,
                "median_ms": round(statistics.median(timings), 2),
                "payload_bytes": len(payload.encode()),
                "rows": sum(len(hunk.lines) for hunk in file.hunks),
            }
        )


if __name__ == "__main__":
    measure()
