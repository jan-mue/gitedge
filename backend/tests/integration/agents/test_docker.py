from typing import TYPE_CHECKING

from pydantic_ai.workspaces import Workspace
from pydantic_ai_harness.docker_sandbox import DockerSandbox, DockerSandboxBackend

from app.agents.main import snapshot_workspace, stop_workspace, workspace_backend

if TYPE_CHECKING:
    from app.agents.dependencies import SetupAgentDeps


async def test_docker_commands_and_files(docker_sandbox_capability: DockerSandbox) -> None:
    sandbox = DockerSandboxBackend(image=docker_sandbox_capability.image, allow_internet_access=False)
    try:
        workspace = Workspace(sandbox)
        assert await workspace.working_dir() == "/workspace"
        literal = "$(touch /workspace/injected)"
        assert (await workspace.run(["printf", "%s", literal])).stdout == literal
        assert not await workspace.exists("injected")
        result = await workspace.run(["sh", "-c", 'printf "%s" "$GREETING"'], env={"GREETING": "hello world"})
        assert result.stdout == "hello world"
        data = bytes(range(256)) * 512
        await workspace.write_bytes("nested/binary", data)
        assert await workspace.read_bytes("nested/binary") == data
        command = "echo called >> count; echo hello; echo warning >&2; exit 7"
        first = await workspace.run(command, shell=True)
        assert (first.exit_code, first.stdout, first.stderr) == (7, "hello\n", "warning\n")
        assert await workspace.read_text("count") == "called\n"
        second = await workspace.run(command, shell=True)
        assert second == first
        assert await workspace.read_text("count") == "called\ncalled\n"
    finally:
        if sandbox.ref is not None:
            await docker_sandbox_capability.destroy(sandbox.ref)


async def test_docker_snapshot_keeps_container_across_turns(docker_setup_agent_deps: SetupAgentDeps) -> None:
    first = await workspace_backend(docker_setup_agent_deps, "docker-first")
    resumed = None
    try:
        await Workspace(first).write_text("state/value", "kept\n")
        snapshot = await snapshot_workspace(first)
        assert first.ref is not None
        assert snapshot == first.ref.id
        await stop_workspace(first)

        resumed = await workspace_backend(docker_setup_agent_deps, "docker-second", snapshot_id=snapshot)
        assert resumed.ref == first.ref
        assert await Workspace(resumed).read_text("state/value") == "kept\n"
        await stop_workspace(resumed)
    finally:
        for backend in (first, resumed):
            if backend is not None and backend.ref is not None:
                await DockerSandbox().destroy(backend.ref)
