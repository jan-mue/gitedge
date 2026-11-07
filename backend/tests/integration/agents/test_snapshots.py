import uuid
from typing import TYPE_CHECKING

from app.clients.sandbox.kubernetes import KubernetesAgentSandbox
from tests.unit.utils.fakes import FakeBlobStorageClient

if TYPE_CHECKING:
    from k8s_agent_sandbox import SandboxClient


async def test_snapshot_resume_and_fork_isolation(agent_sandbox_sdk: SandboxClient) -> None:
    blobs = FakeBlobStorageClient()
    first = KubernetesAgentSandbox(agent_sandbox_sdk, blobs, warmpool="gitedge-agents")
    await first.start(f"setup-{uuid.uuid4()}")
    try:
        assert (
            await first.execute(
                "mkdir -p /usr/local/gitedge-test && echo dependency >/usr/local/gitedge-test/value && echo initial >/workspace/value && chmod 751 /workspace/value && ln -s /workspace/value /workspace/link"
            )
        ).exit_code == 0
        image = await first.snapshot(str(uuid.uuid4()))
    finally:
        await first.stop()
    forks = [KubernetesAgentSandbox(agent_sandbox_sdk, blobs, warmpool="gitedge-agents") for _ in range(2)]
    try:
        for fork in forks:
            await fork.start(f"fork-{uuid.uuid4()}", image)
            result = await fork.execute(
                "cat /usr/local/gitedge-test/value /workspace/link; stat -c %a /workspace/value"
            )
            assert result.stdout == "dependency\ninitial\n751\n"
        await forks[0].execute("echo changed >/workspace/value; rm /usr/local/gitedge-test/value")
        next_image = await forks[0].snapshot(str(uuid.uuid4()))
        assert (await forks[1].execute("cat /workspace/value")).stdout == "initial\n"
        await forks[0].stop()
        await forks[0].start(f"resume-{uuid.uuid4()}", next_image)
        assert (await forks[0].execute("cat /workspace/value")).stdout == "changed\n"
        assert (await forks[0].execute("test -f /usr/local/gitedge-test/value")).exit_code == 1
    finally:
        for fork in forks:
            await fork.stop()
