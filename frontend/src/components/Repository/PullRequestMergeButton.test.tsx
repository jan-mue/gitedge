import { HttpResponse } from "msw"
import { describe, expect, test, vi } from "vitest"
import { handleRepositoriesGetRepository, handleRepositoriesMergePullRequest } from "@/client/msw.gen"
import { server } from "@/test/server"
import { render, screen, waitFor } from "@/test/test-utils"
import { PullRequestMergeButton } from "./PullRequestMergeButton"
import { trackerPulls } from "./tracker-story-fixtures"

vi.mock("@/hooks/useAuth", () => ({ default: () => ({ user: { name: "owner" } }) }))
const { success } = vi.hoisted(() => ({ success: vi.fn() }))
vi.mock("@/hooks/useCustomToast", () => ({ default: () => ({ showSuccessToast: success, showErrorToast: vi.fn() }) }))
const repository = {
  name: "repo",
  owner: "owner",
  created_at: "2026-10-01T00:00:00Z",
  updated_at: "2026-10-01T00:00:00Z",
}

describe("PR merge dropdown", () => {
  test("submits the selected strategy without a success toast", async () => {
    const submit = vi.fn()
    server.use(
      handleRepositoriesGetRepository({ body: repository }),
      handleRepositoriesMergePullRequest(async ({ request }) => {
        submit(await request.json())
        return HttpResponse.json({ ...trackerPulls[0], state: "merged", has_merged: true })
      }),
    )
    const { user } = render(<PullRequestMergeButton owner="owner" repo="repo" pull={trackerPulls[0]} />)
    await waitFor(() => expect(screen.getByRole("button", { name: "Create merge commit" })).toBeEnabled())
    await user.click(screen.getByRole("button", { name: "Choose merge method" }))
    await user.click(screen.getByRole("menuitem", { name: /Rebase and merge/ }))
    await user.click(screen.getByRole("button", { name: "Rebase and merge" }))
    await waitFor(() => expect(submit).toHaveBeenCalledWith({ method: "rebase" }))
    expect(success).not.toHaveBeenCalled()
  })
  test("selects an enabled fallback and hides disabled methods", async () => {
    server.use(
      handleRepositoriesGetRepository({
        body: { ...repository, allow_merge_commit: false, allow_rebase_merge: false },
      }),
    )
    const { user } = render(<PullRequestMergeButton owner="owner" repo="repo" pull={trackerPulls[0]} />)
    await waitFor(() => expect(screen.getByRole("button", { name: "Squash and merge" })).toBeEnabled())
    await user.click(screen.getByRole("button", { name: "Choose merge method" }))
    expect(screen.queryByRole("menuitem", { name: /Create merge commit|Rebase and merge/ })).not.toBeInTheDocument()
  })
  test("explains when all merge methods are disabled", async () => {
    server.use(
      handleRepositoriesGetRepository({
        body: { ...repository, allow_merge_commit: false, allow_rebase_merge: false, allow_squash_merge: false },
      }),
    )
    render(<PullRequestMergeButton owner="owner" repo="repo" pull={trackerPulls[0]} />)
    expect(await screen.findByText("All merge methods are disabled in repository settings.")).toBeVisible()
    expect(screen.queryByRole("button", { name: "Choose merge method" })).not.toBeInTheDocument()
  })
})

test("keeps conflicting filenames visible beside the merge controls", async () => {
  server.use(
    handleRepositoriesGetRepository({ body: repository }),
    handleRepositoriesMergePullRequest(() =>
      HttpResponse.json(
        {
          detail:
            "Merge has conflicts in backend/pyproject.toml, uv.lock. Resolve them on the PR branch before merging.",
        },
        { status: 409 },
      ),
    ),
  )
  const { user } = render(<PullRequestMergeButton owner="owner" repo="repo" pull={trackerPulls[0]} />)
  await waitFor(() => expect(screen.getByRole("button", { name: "Create merge commit" })).toBeEnabled())
  await user.click(screen.getByRole("button", { name: "Create merge commit" }))
  expect(await screen.findByRole("alert")).toHaveTextContent("backend/pyproject.toml, uv.lock")
  expect(screen.getByRole("button", { name: "Choose merge method" })).toBeEnabled()
})
