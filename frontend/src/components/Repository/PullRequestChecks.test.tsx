import { afterEach, describe, expect, test, vi } from "vitest"
import type { ActionRun } from "@/client"
import { handleActionsGetPullRequestChecks } from "@/client/msw.gen"
import { server } from "@/test/server"
import { act, renderWithRouter, screen, waitFor } from "@/test/test-utils"
import { PullRequestChecks } from "./PullRequestChecks"

const run = (status: ActionRun["status"]): ActionRun => ({
  id: "27a368e4-6c47-4da3-b508-277db25d7106",
  workflow: ".gitedge/workflow/ci.yaml",
  name: "CI",
  sha: "a".repeat(40),
  ref: "refs/heads/main",
  actor: "owner",
  event_name: "push",
  status,
  created_at: "2026-10-17T10:00:00Z",
  jobs: [],
})

describe("pull request checks polling", () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  test.each([
    { open: true, status: "queued", interval: 2000 },
    { open: true, status: "running", interval: 2000 },
    { open: false, status: "running", interval: 2000 },
    { open: true, status: "success", interval: 30000 },
    { open: true, status: "failure", interval: 30000 },
    { open: false, status: "success", interval: false },
  ] as const)("uses $interval ms for $status checks on an open=$open PR", async ({ open, status, interval }) => {
    const intervals = vi.spyOn(globalThis, "setInterval")
    server.use(handleActionsGetPullRequestChecks({ body: { head_sha: "a".repeat(40), runs: [run(status)] } }))
    renderWithRouter({ component: () => <PullRequestChecks owner="owner" repo="repo" number={1} open={open} /> })
    await screen.findByText(/Checks for commit/)
    await waitFor(() => {
      const delays = intervals.mock.calls.map((call) => call[1])
      if (interval) expect(delays).toContain(interval)
      else {
        expect(delays).not.toContain(2000)
        expect(delays).not.toContain(30000)
      }
    })
  })

  test("slows polling after active checks finish", async () => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] })
    const intervals = vi.spyOn(globalThis, "setInterval")
    server.use(handleActionsGetPullRequestChecks({ body: { head_sha: "a".repeat(40), runs: [run("running")] } }))
    renderWithRouter({ component: () => <PullRequestChecks owner="owner" repo="repo" number={1} open /> })
    await screen.findByText("Checks are running")
    server.use(handleActionsGetPullRequestChecks({ body: { head_sha: "a".repeat(40), runs: [run("success")] } }))
    await act(() => vi.advanceTimersByTimeAsync(2000))
    await screen.findByText("All checks were successful")
    await waitFor(() => {
      const polling = intervals.mock.calls.map((call) => call[1]).filter((delay) => delay && delay >= 2000)
      expect(polling[polling.length - 1]).toBe(30000)
    })
  })
})
