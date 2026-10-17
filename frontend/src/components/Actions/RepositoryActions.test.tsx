import { HttpResponse } from "msw"
import { describe, expect, test, vi } from "vitest"
import type { ActionRun } from "@/client"
import { handleActionsDispatchWorkflow, handleActionsListRuns, handleActionsListWorkflows } from "@/client/msw.gen"
import { server } from "@/test/server"
import { render, screen, waitFor } from "@/test/test-utils"
import { RepositoryActions } from "./RepositoryActions"
import { RunDetail } from "./RunDetail"

vi.mock("@/hooks/useAuth", () => ({ default: () => ({ user: { name: "owner", is_superuser: false } }) }))

const run: ActionRun = {
  id: "27a368e4-6c47-4da3-b508-277db25d7106",
  workflow: ".gitedge/workflow/ci.yaml",
  name: "CI",
  sha: "a".repeat(40),
  ref: "refs/heads/main",
  actor: "owner",
  event_name: "push",
  status: "success",
  created_at: "2026-10-17T10:00:00Z",
  completed_at: "2026-10-17T10:00:02Z",
  jobs: [
    {
      id: "job",
      key: "test",
      name: "Test",
      status: "success",
      steps: [{ id: "hello", name: "Say hello", status: "success", log: "<script>untrusted</script>" }],
      log: "complete log",
    },
  ],
}

const handlers = () =>
  server.use(
    handleActionsListRuns({ body: [run] }),
    handleActionsListWorkflows({ body: [{ path: ".gitedge/workflow/ci.yaml", name: "CI", dispatch: true }] }),
  )

describe("Actions", () => {
  test("shows real workflow runs and opens a selected run", async () => {
    handlers()
    const select = vi.fn()
    const { user } = render(<RepositoryActions owner="owner" repo="repo" onSelectRun={select} />)
    await user.click(await screen.findByRole("button", { name: /CI.*Commit/ }))
    expect(select).toHaveBeenCalledWith(run.id)
  })

  test("dispatches the selected workflow and revision", async () => {
    handlers()
    const request = vi.fn()
    server.use(
      handleActionsDispatchWorkflow(async ({ request: req }) => {
        request(await req.json())
        return HttpResponse.json(run, { status: 201 })
      }),
    )
    const select = vi.fn()
    const { user } = render(<RepositoryActions owner="owner" repo="repo" onSelectRun={select} />)
    await user.click(await screen.findByRole("button", { name: "ci.yaml" }))
    await user.clear(screen.getByLabelText("Branch, tag, or commit"))
    await user.type(screen.getByLabelText("Branch, tag, or commit"), "release/v1")
    await user.click(screen.getByRole("button", { name: "Run workflow" }))
    await waitFor(() =>
      expect(request).toHaveBeenCalledWith({ workflow: ".gitedge/workflow/ci.yaml", ref: "release/v1", inputs: {} }),
    )
    await waitFor(() => expect(select).toHaveBeenCalledWith(run.id))
  })

  test("expands plain-text step logs without rendering workflow HTML", async () => {
    const { user, container } = render(<RunDetail run={run} canManage={false} cancelling={false} onCancel={vi.fn()} />)
    await user.click(screen.getByRole("button", { name: /Say hello/ }))
    expect(screen.getByText("<script>untrusted</script>")).toBeVisible()
    expect(container.querySelector("script")).toBeNull()
  })

  test("shows an empty repository workflow prompt", async () => {
    server.use(handleActionsListRuns({ body: [] }), handleActionsListWorkflows({ body: [] }))
    render(<RepositoryActions owner="owner" repo="repo" onSelectRun={vi.fn()} />)
    expect(await screen.findByText("Add a workflow in .gitedge/workflow to get started.")).toBeVisible()
  })
})
