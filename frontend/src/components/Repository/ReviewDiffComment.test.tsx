import { HttpResponse } from "msw"
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest"
import type { ReviewPublic } from "@/client"
import { handleReviewsGetCommentContext } from "@/client/msw.gen"
import { server } from "@/test/server"
import { act, render, screen, waitFor } from "@/test/test-utils"
import { comparisonFixture } from "./diff-fixtures"
import { ReviewDiffComment } from "./ReviewDiffComment"

const review: ReviewPublic = {
  id: "review-1",
  author_username: "bob",
  state: "comment",
  body: "",
  base_commit: "a".repeat(40),
  head_commit: "c".repeat(40),
  created_at: "2026-10-16T12:00:00Z",
}
const comment = { path: "src/config.py", side: "old" as const, line: 1, body: "Why change this value?" }
const context = comparisonFixture.files[0].hunks![0]
const props = { owner: "owner", repo: "repo", number: 1, review, comment, commentIndex: 0, outdated: true }

describe("review diff context", () => {
  let enter: (() => void)[]
  beforeEach(() => {
    enter = []
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        constructor(callback: IntersectionObserverCallback) {
          enter.push(() =>
            callback([{ isIntersecting: true } as IntersectionObserverEntry], this as unknown as IntersectionObserver),
          )
        }
        observe() {}
        disconnect() {}
      },
    )
  })
  afterEach(() => vi.unstubAllGlobals())

  test("snapshots render without Git requests and always end at the anchored line", async () => {
    const requested = vi.fn()
    server.use(
      handleReviewsGetCommentContext(() => {
        requested()
        return HttpResponse.json(context)
      }),
    )
    render(<ReviewDiffComment {...props} comment={{ ...comment, context }} />)
    expect(document.querySelector('[data-comment-anchor="true"] code')).toHaveTextContent("timeout = 12")
    expect(document.querySelectorAll(".diff-code-row")).toHaveLength(1)
    expect(document.querySelector(".review-diff-context .diff-cell:last-child")).toHaveAttribute(
      "data-comment-anchor",
      "true",
    )
    expect(enter).toHaveLength(0)
    expect(requested).not.toHaveBeenCalled()
    expect(screen.getByText(comment.body)).toBeVisible()
  })

  test("legacy context loads only when near the viewport and uses the review's immutable identity", async () => {
    const requested: string[] = []
    server.use(
      handleReviewsGetCommentContext(({ request }) => {
        requested.push(request.url)
        return HttpResponse.json(context)
      }),
    )
    render(<ReviewDiffComment {...props} />)
    expect(requested).toHaveLength(0)
    act(() => enter[0]())
    await waitFor(() =>
      expect(document.querySelector('[data-comment-anchor="true"] code')).toHaveTextContent("timeout = 12"),
    )
    expect(requested).toHaveLength(1)
    expect(requested[0]).toContain("/reviews/review-1/comments/0/context")
    expect(document.querySelectorAll(".diff-code-row")).toHaveLength(1)
  })

  test("keeps the comment visible on errors and retries without losing the thread", async () => {
    let failed = true
    server.use(
      handleReviewsGetCommentContext(() =>
        failed ? new HttpResponse(null, { status: 503 }) : HttpResponse.json(context),
      ),
    )
    const { user } = render(<ReviewDiffComment {...props} />)
    act(() => enter[0]())
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load diff context")
    expect(screen.getByText(comment.body)).toBeVisible()
    failed = false
    await user.click(screen.getByRole("button", { name: "Retry" }))
    await waitFor(() =>
      expect(document.querySelector('[data-comment-anchor="true"] code')).toHaveTextContent("timeout = 12"),
    )
  })

  test("does not substitute another line if the original anchor is unavailable", async () => {
    render(<ReviewDiffComment {...props} comment={{ ...comment, line: 999, context }} />)
    expect(screen.getByText("Diff context is unavailable for this line.")).toBeVisible()
    expect(document.querySelector(".diff-code-row")).toBeNull()
  })
})
