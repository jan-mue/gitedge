import { HttpResponse } from "msw"
import { afterEach, expect, test } from "vitest"
import type { ActionJob } from "@/client"
import { client } from "@/client/client.gen"
import { handleActionsLogEvents, handleActionsLogHistory } from "@/client/msw.gen"
import { server } from "@/test/server"
import { render, screen, waitFor } from "@/test/test-utils"
import { JobLogs } from "./JobLogs"

const job: ActionJob = {
  id: "job",
  key: "test",
  name: "Test",
  status: "running",
  attempt_id: "11111111-1111-4111-8111-111111111111",
  steps: [{ id: "hello", name: "Hello", status: "running" }],
}
const event = (seq: number, msg: string) =>
  `id: ${seq}\nevent: log\ndata: ${JSON.stringify({ seq, msg, step_id: "hello", end: true })}\n\n`

const original = client.getConfig()
afterEach(() => {
  client.setConfig(original)
})

test("resumes authenticated streams without repeating records after a bounded session closes", async () => {
  client.setConfig({ auth: () => "test-session" })
  const cursors: string[] = []
  server.use(
    handleActionsLogHistory({
      body: {
        attempt_id: job.attempt_id!,
        next_seq: 1,
        complete: false,
        records: [{ seq: 1, msg: "first", step_id: "hello", end: true }],
      },
    }),
    handleActionsLogEvents(({ request }) => {
      expect(request.headers.get("authorization")).toBe("Bearer test-session")
      expect(new URL(request.url).searchParams.has("token")).toBe(false)
      const cursor = request.headers.get("Last-Event-ID") || ""
      cursors.push(cursor)
      return new HttpResponse(
        cursor === "1"
          ? event(1, "first") + event(2, "second")
          : `${event(2, "second") + event(3, "third")}event: end\ndata: {"last_seq":3}\n\n`,
        {
          headers: { "Content-Type": "text/event-stream" },
        },
      )
    }),
  )
  const { container } = render(<JobLogs owner="owner" repo="repo" runId="run" job={job} />)
  await waitFor(() => expect(container.querySelector("details pre")?.textContent).toBe("first\nsecond\nthird\n"))
  expect(cursors).toEqual(["1", "2"])
})

test("leaving the job aborts the authenticated stream and its reconnect loop", async () => {
  const signals: AbortSignal[] = []
  const interceptor = client.interceptors.request.use((request) => {
    if (new URL(request.url).pathname.endsWith("/logs/events")) signals.push(request.signal)
    return request
  })
  server.use(
    handleActionsLogHistory({ body: { attempt_id: job.attempt_id!, next_seq: 0, complete: false, records: [] } }),
    handleActionsLogEvents(
      () => new HttpResponse(event(1, "streaming"), { headers: { "Content-Type": "text/event-stream" } }),
    ),
  )
  try {
    const view = render(<JobLogs owner="owner" repo="repo" runId="run" job={job} />)
    await screen.findByText("Live output")
    view.unmount()
    expect(signals.length).toBeGreaterThan(0)
    expect(signals.every((signal) => signal.aborted)).toBe(true)
  } finally {
    client.interceptors.request.eject(interceptor)
  }
})

test("large streamed output keeps a bounded view and offers the full download", async () => {
  server.use(
    handleActionsLogHistory({ body: { attempt_id: job.attempt_id!, next_seq: 0, complete: false, records: [] } }),
    handleActionsLogEvents(
      () =>
        new HttpResponse(
          `${Array.from({ length: 200 }, (_, index) => event(index + 1, `${index + 1}:${"🔑".repeat(4000)}`)).join("")}event: end\ndata: {"last_seq":200}\n\n`,
          {
            headers: { "Content-Type": "text/event-stream" },
          },
        ),
    ),
  )
  const { container } = render(<JobLogs owner="owner" repo="repo" runId="run" job={job} />)
  await screen.findByText("Showing recent output. Download the log for the complete history.")
  const text = container.querySelector("details pre")?.textContent || ""
  expect(text.length).toBeLessThanOrEqual(513 * 1024)
  expect(text).toContain("200:")
  expect(screen.getByRole("button", { name: "Download log" })).toBeVisible()
})
