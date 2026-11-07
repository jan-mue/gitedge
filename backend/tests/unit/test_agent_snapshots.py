import json
import subprocess
import sys
from typing import TYPE_CHECKING

from app.constants import RESOURCES_DIR

if TYPE_CHECKING:
    from pathlib import Path

SCRIPT = RESOURCES_DIR / "agents" / "snapshot.py"


def snapshot_command(mode: str, root: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            mode,
            "--root",
            str(root),
            "--baseline",
            str(root / "opt/gitedge/base-files.json"),
            "--archive",
            str(root / "opt/gitedge/image.tar.gz"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_rootfs_delta_roundtrip_includes_dependencies_and_deletions(tmp_path: Path) -> None:
    original, resumed = tmp_path / "original", tmp_path / "resumed"
    for root in [original, resumed]:
        (root / "opt/gitedge").mkdir(parents=True)
        (root / "usr/local/lib").mkdir(parents=True)
        (root / "workspace").mkdir()
        (root / "usr/local/lib/old-dependency").write_text("old")
        (root / "workspace/unchanged").write_text("baseline")
        snapshot_command("baseline", root)
    (original / "usr/local/lib/old-dependency").unlink()
    (original / "usr/local/lib/new-dependency").write_text("installed dependency")
    executable = original / "workspace/run"
    executable.write_text("#!/bin/sh\necho hello\n")
    executable.chmod(0o751)
    (original / "workspace/link").symlink_to("run")
    snapshot_command("capture", original)
    (resumed / "opt/gitedge/image.tar.gz").write_bytes((original / "opt/gitedge/image.tar.gz").read_bytes())
    snapshot_command("restore", resumed)
    assert not (resumed / "usr/local/lib/old-dependency").exists()
    assert (resumed / "usr/local/lib/new-dependency").read_text() == "installed dependency"
    assert (resumed / "workspace/link").read_text() == "#!/bin/sh\necho hello\n"
    assert (resumed / "workspace/run").stat().st_mode & 0o777 == 0o751
    assert (resumed / "workspace/unchanged").read_text() == "baseline"
    assert json.loads((resumed / "opt/gitedge/base-files.json").read_text())
