import shlex
import shutil
import uuid
from typing import TYPE_CHECKING

import pytest
from pydantic_ai.workspaces import Workspace

from app.agents.main import snapshot_workspace, stop_workspace, workspace_backend

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType

    from pydantic_ai_harness.smol_sandbox import SmolSandboxBackend

    from app.agents.dependencies import SetupAgentDeps


@pytest.fixture
def native_smol_checkpoints() -> ModuleType:
    if shutil.which("mkfs.ext4") is None:
        pytest.skip("Native Smol checkpoints require e2fsprogs (mkfs.ext4) on the host PATH")
    return pytest.importorskip("smol")


async def test_native_checkpoint_resume_and_fork_isolation(
    native_smol_checkpoints: ModuleType,
    agent_sandbox: SmolSandboxBackend,
    setup_agent_deps: SetupAgentDeps,
    tmp_path: Path,
) -> None:
    smol = native_smol_checkpoints
    snapshots: list[str] = []
    forks = []
    first = Workspace(agent_sandbox)
    try:
        assert (
            await first.run(
                "mkdir -p /usr/local/gitedge-test && echo dependency >/usr/local/gitedge-test/value && echo initial >/workspace/value && chmod 751 /workspace/value && ln -s /workspace/value /workspace/link",
                shell=True,
            )
        ).exit_code == 0
        image = await snapshot_workspace(agent_sandbox, checkpoint_dir=tmp_path)
        snapshots.append(image)
        await stop_workspace(agent_sandbox)
        for _ in range(2):
            fork = await workspace_backend(setup_agent_deps, f"fork-{uuid.uuid4()}", snapshot_id=image)
            forks.append(fork)
            result = await Workspace(fork).run(
                "cat /usr/local/gitedge-test/value /workspace/link; stat -c %a /workspace/value", shell=True
            )
            assert result.stdout == "dependency\ninitial\n751\n"
        await Workspace(forks[0]).run("echo changed >/workspace/value; rm /usr/local/gitedge-test/value", shell=True)
        next_image = await snapshot_workspace(forks[0], checkpoint_dir=tmp_path)
        snapshots.append(next_image)
        assert (await Workspace(forks[1]).run(["cat", "/workspace/value"])).stdout == "initial\n"
        await stop_workspace(forks[0])
        forks[0] = await workspace_backend(setup_agent_deps, f"resume-{uuid.uuid4()}", snapshot_id=next_image)
        assert (await Workspace(forks[0]).run(["cat", "/workspace/value"])).stdout == "changed\n"
        assert (await Workspace(forks[0]).run(["test", "-f", "/usr/local/gitedge-test/value"])).exit_code == 1
    finally:
        for fork in forks:
            await stop_workspace(fork)
        for image in snapshots:
            await smol.AsyncMachine.delete_checkpoint(image, smol.ConnectOptions(target="local"))


async def test_native_checkpoint_preserves_a_running_process(
    native_smol_checkpoints: ModuleType,
    agent_sandbox: SmolSandboxBackend,
    setup_agent_deps: SetupAgentDeps,
    tmp_path: Path,
) -> None:
    smol = native_smol_checkpoints
    token = uuid.uuid4().hex
    program = (
        "import os,time; from pathlib import Path; "
        f"value={token!r}; Path('/workspace/ready').write_text(str(os.getpid())); "
        "\nwhile not Path('/workspace/release').exists(): time.sleep(0.01)\n"
        "Path('/workspace/result').write_text(value); time.sleep(600)"
    )
    restored = None
    image = None
    try:
        launch = (
            f"nohup setsid python3 -c {shlex.quote(program)} >/dev/null 2>&1 </dev/null & "
            "while ! test -f /workspace/ready; do sleep 0.01; done"
        )
        await Workspace(agent_sandbox).run(["bash", "-c", launch], timeout=10)
        ready = await Workspace(agent_sandbox).run(
            [
                "python3",
                "-c",
                "from pathlib import Path; import time\nwhile not Path('/workspace/ready').exists(): time.sleep(0.01)\nprint(Path('/workspace/ready').read_text())",
            ],
            timeout=10,
        )
        pid = ready.stdout.strip()
        assert pid.isdigit()
        image = await snapshot_workspace(agent_sandbox, checkpoint_dir=tmp_path)
        await stop_workspace(agent_sandbox)
        restored = await workspace_backend(setup_agent_deps, "process-restore", snapshot_id=image)
        workspace = Workspace(restored)
        assert (
            await workspace.run(["python3", "-c", "import os,sys; os.kill(int(sys.argv[1]), 0)", pid])
        ).exit_code == 0
        await workspace.write_text("/workspace/release", "continue")
        result = await workspace.run(
            [
                "python3",
                "-c",
                "from pathlib import Path; import time\nwhile not Path('/workspace/result').exists(): time.sleep(0.01)\nprint(Path('/workspace/result').read_text())",
            ],
            timeout=10,
        )
        assert result.stdout.strip() == token
    finally:
        if restored is not None:
            await stop_workspace(restored)
        if image is not None:
            await smol.AsyncMachine.delete_checkpoint(image, smol.ConnectOptions(target="local"))
