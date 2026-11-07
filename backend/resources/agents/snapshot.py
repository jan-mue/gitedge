"""Filesystem-delta snapshots executed inside an agent-sandbox, never on the backend."""

import argparse
import hashlib
import io
import json
import os
import stat
import tarfile
from pathlib import Path

EXCLUDED = (
    "proc",
    "sys",
    "dev",
    "run",
    "tmp",
    "runtime",
    "var/run",
    "var/log",
    "etc/hosts",
    "etc/hostname",
    "etc/resolv.conf",
    "opt/gitedge/snapshot.py",
    "opt/gitedge/base-files.json",
    "opt/gitedge/image.tar.gz",
    "opt/gitedge/restored",
    ".dockerenv",
)


def excluded(path: str) -> bool:
    """Keep runtime mounts and snapshot bookkeeping out of filesystem state."""
    return any(path == prefix or path.startswith(prefix + "/") for prefix in EXCLUDED)


def inventory(root: Path) -> dict[str, str]:
    """Hash contents, ownership, modes and symlink targets against the warm-pool image."""
    result = {}
    for directory, subdirs, files in os.walk(root, followlinks=False):
        relative = Path(directory).relative_to(root)
        subdirs[:] = sorted(name for name in subdirs if not excluded((relative / name).as_posix()))
        for name in [*subdirs, *sorted(files)]:
            path = Path(directory) / name
            key = path.relative_to(root).as_posix()
            if excluded(key):
                continue
            try:
                info = path.lstat()
                metadata = f"{info.st_mode}:{info.st_uid}:{info.st_gid}:"
                if stat.S_ISLNK(info.st_mode):
                    content = os.readlink(path).encode()
                elif stat.S_ISREG(info.st_mode):
                    with path.open("rb") as source:
                        content = hashlib.file_digest(source, "sha256").digest()
                elif stat.S_ISDIR(info.st_mode):
                    content = b""
                else:
                    continue
                result[key] = hashlib.sha256(metadata.encode() + content).hexdigest()
            except FileNotFoundError:
                # Transient process files may disappear during traversal.
                continue
    return result


def capture(root: Path, baseline: Path, destination: Path) -> None:
    """Save all changed system/project files and explicit deletions, not just workspace prefixes."""
    base = json.loads(baseline.read_text())
    current = inventory(root)
    metadata = json.dumps(
        {
            "version": 1,
            "base": hashlib.sha256(baseline.read_bytes()).hexdigest(),
            "deleted": sorted(set(base) - set(current)),
        }
    ).encode()
    with tarfile.open(destination, "w:gz", dereference=False) as archive:
        header = tarfile.TarInfo(".gitedge-snapshot.json")
        header.size = len(metadata)
        archive.addfile(header, io.BytesIO(metadata))
        for path, fingerprint in sorted(current.items()):
            if base.get(path) != fingerprint:
                archive.add(root / path, arcname=path, recursive=False)


def restore(root: Path, baseline: Path, source: Path) -> None:
    """Apply an immutable delta to the same warm-pool image, including deleted files."""
    with tarfile.open(source, "r:gz") as archive:
        entry = archive.extractfile(".gitedge-snapshot.json")
        if entry is None:
            raise ValueError("Missing snapshot metadata")
        metadata = json.load(entry)
        if metadata["version"] != 1 or metadata["base"] != hashlib.sha256(baseline.read_bytes()).hexdigest():
            raise ValueError("Warm-pool image changed; rebuild the setup snapshot")
        for name in sorted(metadata["deleted"], key=lambda value: value.count("/"), reverse=True):
            path = Path(name)
            if path.is_absolute() or ".." in path.parts or excluded(name):
                raise ValueError("Invalid snapshot path")
            target = root / path
            if target.is_symlink() or target.is_file():
                target.unlink(missing_ok=True)
            elif target.is_dir():
                target.rmdir()
        for member in archive.getmembers():
            if member.name == ".gitedge-snapshot.json":
                continue
            path = Path(member.name)
            if path.is_absolute() or ".." in path.parts or excluded(member.name):
                raise ValueError("Invalid snapshot path")
            target = root / path
            if member.isfile() and target.exists() and not target.is_dir():
                target.unlink()
            # This runs inside the disposable sandbox and intentionally restores
            # system ownership, executable modes and absolute symlink targets.
            archive.extract(member, path=root, filter="fully_trusted")


def main() -> None:
    """Create a baseline or capture/restore an image delta inside the sandbox."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["baseline", "capture", "restore"])
    parser.add_argument("--root", type=Path, default=Path("/"))
    parser.add_argument("--baseline", type=Path, default=Path("/opt/gitedge/base-files.json"))
    parser.add_argument("--archive", type=Path, default=Path("/opt/gitedge/image.tar.gz"))
    args = parser.parse_args()
    if args.mode == "baseline":
        if not args.baseline.exists():
            args.baseline.write_text(json.dumps(inventory(args.root), sort_keys=True))
    elif args.mode == "capture":
        capture(args.root, args.baseline, args.archive)
    else:
        restore(args.root, args.baseline, args.archive)


if __name__ == "__main__":
    main()
