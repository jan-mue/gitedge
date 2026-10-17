import { HttpResponse } from "msw"
import { beforeEach, describe, expect, test, vi } from "vitest"
import {
  handleRepositoriesGetPullRequestMergeability,
  handleRepositoriesGetRepository,
  handleRepositoriesMergePullRequest,
} from "@/client/msw.gen"
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

const mergeable = { mergeable: true, base_commit: "a".repeat(40), head_commit: "b".repeat(40), conflicting_files: [] }
beforeEach(() => server.use(handleRepositoriesGetPullRequestMergeability({ body: mergeable })))

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
    await waitFor(() =>
      expect(submit).toHaveBeenCalledWith({
        method: "rebase",
        base_commit: mergeable.base_commit,
        head_commit: mergeable.head_commit,
      }),
    )
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

test("shows conflicts and disables merging before any merge request, then rechecks after resolution", async () => {
  const submit = vi.fn()
  server.use(
    handleRepositoriesGetRepository({ body: repository }),
    handleRepositoriesGetPullRequestMergeability({
      body: {
        ...mergeable,
        mergeable: false,
        conflicting_files: ["backend/pyproject.toml", "uv.lock"],
      },
    }),
    handleRepositoriesMergePullRequest(() => {
      submit()
      return HttpResponse.json(trackerPulls[0])
    }),
  )
  const { user } = render(<PullRequestMergeButton owner="owner" repo="repo" pull={trackerPulls[0]} />)
  expect(await screen.findByText("This branch has conflicts that must be resolved")).toBeVisible()
  expect(screen.getByRole("list", { name: "Conflicting files" })).toHaveTextContent("uv.lock")
  expect(screen.getByTestId("merge-pr")).toBeDisabled()
  expect(screen.getByRole("button", { name: "Choose merge method" })).toBeEnabled()
  await user.click(screen.getByTestId("merge-pr"))
  expect(submit).not.toHaveBeenCalled()
  server.use(handleRepositoriesGetPullRequestMergeability({ body: mergeable }))
  await user.click(screen.getByRole("button", { name: "Check again" }))
  await waitFor(() => expect(screen.getByTestId("merge-pr")).toBeEnabled())
  expect(screen.queryByRole("list", { name: "Conflicting files" })).not.toBeInTheDocument()
})

test("keeps merging disabled while the check is loading or fails", async () => {
  let fail: (() => void) | undefined
  const pending = new Promise<void>((resolve) => {
    fail = resolve
  })
  server.use(
    handleRepositoriesGetRepository({ body: repository }),
    handleRepositoriesGetPullRequestMergeability(async () => {
      await pending
      return HttpResponse.json({ detail: "Unavailable" }, { status: 503 })
    }),
  )
  const { user } = render(<PullRequestMergeButton owner="owner" repo="repo" pull={trackerPulls[0]} />)
  expect(await screen.findByText("Checking whether this pull request can be merged…")).toBeVisible()
  expect(screen.getByTestId("merge-pr")).toBeDisabled()
  fail?.()
  expect(await screen.findByText("Unable to check for merge conflicts", {}, { timeout: 5000 })).toBeVisible()
  expect(screen.getByTestId("merge-pr")).toBeDisabled()
  server.use(handleRepositoriesGetPullRequestMergeability({ body: mergeable }))
  await user.click(screen.getByRole("button", { name: "Check again" }))
  await waitFor(() => expect(screen.getByTestId("merge-pr")).toBeEnabled())
})
