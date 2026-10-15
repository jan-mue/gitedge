import { HttpResponse } from "msw"
import { beforeEach, describe, expect, test, vi } from "vitest"
import type { ReviewWorkspacePublic } from "@/client"
import {
  handleReviewsGetWorkspace,
  handleReviewsMarkReviewed,
  handleReviewsSaveDraft,
  handleReviewsSubmitReview,
} from "@/client/msw.gen"
import { server } from "@/test/server"
import { render, screen, waitFor } from "@/test/test-utils"
import { comparisonFixture } from "./diff-fixtures"
import { PullRequestFiles } from "./PullRequestFiles"

vi.mock("@/hooks/useCustomToast", () => ({ default: () => ({ showSuccessToast: vi.fn(), showErrorToast: vi.fn() }) }))

const props = {
  owner: "owner",
  repo: "repo",
  number: 1,
  changes: comparisonFixture,
  reviews: [],
  author: "owner",
  isOpen: true,
}

describe("PullRequestFiles", () => {
  let workspace: ReviewWorkspacePublic
  beforeEach(() => {
    workspace = { draft: null, reviewed_paths: [] }
    server.use(
      handleReviewsGetWorkspace(() => HttpResponse.json(workspace)),
      handleReviewsSaveDraft(async ({ request }) => {
        workspace = { ...workspace, draft: await request.json() }
        return HttpResponse.json(workspace)
      }),
    )
  })

  test("authors can comment or request changes but cannot approve", async () => {
    const { user } = render(<PullRequestFiles {...props} username="owner" />)
    await waitFor(() => expect(screen.getByRole("button", { name: "Review" })).toBeEnabled())
    await user.click(screen.getByRole("button", { name: "Review" }))
    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled()
    await user.type(screen.getByRole("textbox", { name: "Review comment" }), "A note")
    expect(screen.getByRole("button", { name: "Comment" })).toBeEnabled()
    expect(screen.getByRole("button", { name: "Request changes" })).toBeEnabled()
  })

  test("saves private line comments, reviewed progress and submits them as one review", async () => {
    const submit = vi.fn()
    server.use(
      handleReviewsMarkReviewed(async ({ request }) => {
        const body = (await request.json()) as { path: string }
        workspace = { ...workspace, reviewed_paths: [body.path] }
        return HttpResponse.json(workspace)
      }),
      handleReviewsSubmitReview(async ({ request }) => {
        const body = await request.json()
        submit(body)
        workspace = { ...workspace, draft: null }
        return HttpResponse.json(
          { ...body, id: "review-1", author_username: "reviewer", created_at: "2026-10-14T00:00:00Z" },
          { status: 201 },
        )
      }),
    )
    const { user } = render(<PullRequestFiles {...props} username="reviewer" />)
    await user.click(await screen.findByRole("button", { name: "Comment on src/config.py new line 1" }))
    await user.type(screen.getByRole("textbox", { name: "Line comment" }), "Please add a test")
    await user.click(screen.getByRole("button", { name: "Add to review" }))
    expect(await screen.findByText("Please add a test")).toBeInTheDocument()
    expect(submit).not.toHaveBeenCalled()
    await user.click(screen.getByRole("checkbox", { name: "Mark src/config.py as viewed" }))
    expect(await screen.findByText("1 / 2 files viewed")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Review (1)" }))
    await user.type(screen.getByRole("textbox", { name: "Review comment" }), "Looks good once tested")
    await user.click(screen.getByRole("button", { name: "Approve" }))
    await waitFor(() =>
      expect(submit).toHaveBeenCalledWith({
        base_commit: comparisonFixture.base_commit,
        head_commit: comparisonFixture.head_commit,
        state: "approved",
        body: "Looks good once tested",
        comments: [{ path: "src/config.py", side: "new", line: 1, body: "Please add a test" }],
      }),
    )
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
  })

  test("a stale draft is preserved and requires restarting before review", async () => {
    workspace.draft = {
      base_commit: comparisonFixture.base_commit!,
      head_commit: "c".repeat(40),
      comments: [],
      body: "Earlier draft",
    }
    render(<PullRequestFiles {...props} username="reviewer" />)
    expect(await screen.findByText("The branches changed since you started this review.")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Review" })).toBeDisabled()
    expect(screen.getByText("Earlier draft")).toBeInTheDocument()
  })
})
