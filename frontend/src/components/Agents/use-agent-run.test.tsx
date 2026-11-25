import type { Message } from "@ag-ui/client"
import { beforeEach, describe, expect, test, vi } from "vitest"
import { Button } from "@/components/design-system"
import { render, screen, waitFor } from "@/test/test-utils"
import type { RunPublic } from "./api"
import { useAgentRun } from "./use-agent-run"

const client = vi.hoisted(() => ({
  runAgent: vi.fn(
    () =>
      new Promise<void>(() => {
        // Keep the stream pending to exercise effect teardown.
      }),
  ),
  abortRun: vi.fn(),
}))

vi.mock("@ag-ui/client", () => ({
  HttpAgent: class {
    messages: Message[]

    constructor({ initialMessages }: { initialMessages: Message[] }) {
      this.messages = initialMessages
    }

    runAgent = client.runAgent
    abortRun = client.abortRun
  },
}))

const activeRun: RunPublic = {
  id: "run-1",
  session_id: "session-1",
  status: "running",
  invocation_id: null,
  error: null,
  prompt: "Hello",
  model: "ollama:test",
  created_at: "2026-11-19T00:00:00Z",
  finished_at: null,
}

const Probe = ({ run }: { run?: RunPublic }) => {
  const live = useAgentRun("session-1", run, [], true)
  return (
    <>
      <Button disabled={live.busy}>Send message</Button>
      <Button onClick={live.reconnect}>Reconnect</Button>
    </>
  )
}

describe("agent stream lifecycle", () => {
  beforeEach(() => vi.clearAllMocks())

  test("releases the composer when the active run finishes", async () => {
    const { rerender } = render(<Probe run={activeRun} />)
    await waitFor(() => expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled())

    rerender(<Probe />)

    await waitFor(() => expect(screen.getByRole("button", { name: "Send message" })).toBeEnabled())
    expect(client.abortRun).toHaveBeenCalledOnce()
  })

  test("reconnect aborts the old stream and starts a new subscription", async () => {
    const { user } = render(<Probe run={activeRun} />)
    await waitFor(() => expect(client.runAgent).toHaveBeenCalledOnce())

    await user.click(screen.getByRole("button", { name: "Reconnect" }))

    await waitFor(() => expect(client.runAgent).toHaveBeenCalledTimes(2))
    expect(client.abortRun).toHaveBeenCalledOnce()
  })
})
