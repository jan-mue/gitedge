from typing import TYPE_CHECKING

import pytest
from pydantic_ai.workspaces import Workspace

if TYPE_CHECKING:
    from pydantic_ai_harness.smol_sandbox import SmolSandbox


async def test_native_smol_commands_and_files(smol_sandbox_capability: SmolSandbox) -> None:
    sandbox_module = pytest.importorskip("pydantic_ai_harness.smol_sandbox")
    sandbox = sandbox_module.SmolSandboxBackend(image=smol_sandbox_capability.image)
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
            await sandbox_module.SmolSandbox().destroy(sandbox.ref)
