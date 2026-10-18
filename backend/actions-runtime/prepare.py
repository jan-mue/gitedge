"""Prepare action source at image-build time, including nested composite actions."""

# ruff: noqa: S603 - argument arrays contain validated action references; no shell is used

import json
import re
import shutil
import subprocess
from pathlib import Path

import yaml

root = Path("/opt/gitedge/action-cache")
root.mkdir(parents=True, exist_ok=True)
manifest: dict[str, str] = {}
queue = Path("/build/actions.txt").read_text().splitlines()
seen: set[str] = set()
while queue:
    action = queue.pop()
    if action in seen or action.startswith(("./", "docker://")):
        continue
    seen.add(action)
    if not re.fullmatch(r"[\w.-]+/[\w.-]+(?:/[\w./-]+)?@[^\s]+", action):
        raise ValueError(f"Invalid action reference: {action}")
    repository_path, ref = action.rsplit("@", 1)
    if ref.startswith("-") or any(part in {".", ".."} for part in repository_path.split("/")):
        raise ValueError(f"Unsafe action reference: {action}")
    repository = "/".join(repository_path.split("/")[:2])
    directory = root / (repository.replace("/", "-") + ".git")
    if not directory.exists():
        subprocess.run(["/usr/bin/git", "init", "--bare", str(directory)], check=True, capture_output=True)
    subprocess.run(
        ["/usr/bin/git", "-C", str(directory), "fetch", "--depth=1", f"https://github.com/{repository}.git", ref],
        check=True,
    )
    sha = subprocess.check_output(["/usr/bin/git", "-C", str(directory), "rev-parse", "FETCH_HEAD"], text=True).strip()
    tree = Path("/opt/gitedge/actions") / repository.replace("/", "-") / sha
    tree.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["/usr/bin/git", "--git-dir", str(directory), "--work-tree", str(tree), "checkout", "--force", sha, "--", "."],
        check=True,
    )
    manifest[f"{repository}@{ref}"] = str(tree.relative_to("/opt/gitedge/actions"))
    subprocess.run(["/usr/bin/git", "-C", str(directory), "update-ref", f"refs/gitedge/{sha}", sha], check=True)
    subpath = "/".join(repository_path.split("/")[2:])
    for filename in ("action.yml", "action.yaml"):
        location = "/".join(part for part in (subpath, filename) if part)
        result = subprocess.run(
            ["/usr/bin/git", "-C", str(directory), "show", f"{sha}:{location}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            definition = yaml.safe_load(result.stdout)
            for step in definition.get("runs", {}).get("steps", []):
                uses = step.get("uses", "")
                if re.match(r"^[\w.-]+/[\w.-]+(?:/[\w./-]+)?@[^\s]+$", uses):
                    queue.append(uses)
            break
Path("/opt/gitedge/actions/manifest.json").write_text(json.dumps(manifest, sort_keys=True))
shutil.rmtree(root)
