from typing import TYPE_CHECKING

from ag_ui.core import CustomEvent
from pydantic_ai_harness.shell import CommandOutputEvent, CommandStartedEvent

from app.agents.coding import StableAGUIEventStream

if TYPE_CHECKING:
    from pydantic_ai.messages import CapabilityEvent


async def command_events(stream: StableAGUIEventStream, event: CapabilityEvent) -> list[CustomEvent]:
    result = []
    async for output in stream.handle_event(event):
        assert isinstance(output, CustomEvent)
        result.append(output)
    return result


async def test_shell_output_is_forwarded_as_command_logs() -> None:
    stream = StableAGUIEventStream(run_id="run", thread_id="session")
    chunks = ["hello ", "world\n"]
    output = []
    for chunk in chunks:
        output.extend(await command_events(stream, CommandOutputEvent(tool_call_id="shell-call", text=chunk)))
    assert all(isinstance(event, CustomEvent) for event in output)
    assert [event.name for event in output] == ["bash_output", "bash_output"]
    assert [event.value for event in output] == [
        {"command_id": "shell-call", "stream": "combined", "chunk": chunk, "sequence": sequence}
        for sequence, chunk in enumerate(chunks)
    ]


async def test_command_logs_are_sequenced_per_tool_call() -> None:
    stream = StableAGUIEventStream(run_id="run", thread_id="session")
    output = []
    for call in ["first", "second", "first"]:
        output.extend(await command_events(stream, CommandOutputEvent(tool_call_id=call, text="chunk")))
    assert [event.value["sequence"] for event in output] == [0, 0, 1]
    assert [event.value["command_id"] for event in output] == ["first", "second", "first"]


async def test_reconstructed_stream_reproduces_command_logs() -> None:
    events = [CommandOutputEvent(tool_call_id="shell-call", text=chunk) for chunk in ["hello", " world"]]
    original = StableAGUIEventStream(run_id="run", thread_id="session")
    restored = StableAGUIEventStream(run_id="run", thread_id="session")
    first = [output.value for event in events for output in await command_events(original, event)]
    replay = [output.value for event in events for output in await command_events(restored, event)]
    assert replay == first


async def test_nonoutput_shell_events_are_not_exposed_as_command_logs() -> None:
    stream = StableAGUIEventStream(run_id="run", thread_id="session")
    event = CommandStartedEvent(tool_call_id="shell-call", command="echo hello", pid=123)
    assert [output async for output in stream.handle_event(event)] == []
