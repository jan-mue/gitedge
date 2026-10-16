import { HttpResponse } from "msw"
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest"
import type { ReviewPublic } from "@/client"
import { handleRepositoriesGetDiffFile } from "@/client/msw.gen"
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

  test("loads only near the viewport and shares immutable highlighted context between comments", async () => {
    const requested: URL[] = []
    server.use(
      handleRepositoriesGetDiffFile(({ request }) => {
        requested.push(new URL(request.url))
        return HttpResponse.json(comparisonFixture.files[0])
      }),
    )
    render(
      <>
        <ReviewDiffComment owner="owner" repo="repo" review={review} comment={comment} outdated />
        <ReviewDiffComment
          owner="owner"
          repo="repo"
          review={review}
          comment={{ ...comment, side: "new", body: "Add a test." }}
          outdated
        />
      </>,
    )
    expect(screen.getByText(comment.body)).toBeInTheDocument()
    expect(requested).toHaveLength(0)
    act(() => {
      for (const callback of enter) callback()
    })
    await waitFor(() => expect(document.querySelectorAll('[data-comment-anchor="true"]')).toHaveLength(2))
    expect(requested).toHaveLength(1)
    expect(requested[0].searchParams.get("head")).toBe(review.head_commit)
    expect(requested[0].searchParams.get("base")).toBe(review.base_commit)
    expect([...document.querySelectorAll('[data-comment-anchor="true"] code')].map((node) => node.textContent)).toEqual(
      ["timeout = 12", "timeout = 42"],
    )
    expect(screen.getAllByText("Outdated")).toHaveLength(2)
    expect(document.querySelector('[data-syntax="literal-number"][data-changed="true"]')).toBeInTheDocument()
  })

  test("keeps the comment visible when context fails and supports retry", async () => {
    let failed = true
    server.use(
      handleRepositoriesGetDiffFile(() =>
        failed ? new HttpResponse(null, { status: 503 }) : HttpResponse.json(comparisonFixture.files[0]),
      ),
    )
    const { user } = render(
      <ReviewDiffComment owner="owner" repo="repo" review={review} comment={comment} outdated={false} />,
    )
    act(() => enter[0]())
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load diff context")
    expect(screen.getByText(comment.body)).toBeVisible()
    failed = false
    await user.click(screen.getByRole("button", { name: "Retry" }))
    await waitFor(() =>
      expect(document.querySelector('[data-comment-anchor="true"] code')).toHaveTextContent("timeout = 12"),
    )
  })

  test("does not substitute a different line if the original anchor is unavailable", async () => {
    server.use(handleRepositoriesGetDiffFile({ body: comparisonFixture.files[0] }))
    render(<ReviewDiffComment owner="owner" repo="repo" review={review} comment={{ ...comment, line: 999 }} outdated />)
    act(() => enter[0]())
    expect(await screen.findByText("Diff context is unavailable for this line.")).toBeVisible()
    expect(document.querySelector(".diff-code-row")).toBeNull()
    expect(screen.getByText(comment.body)).toBeVisible()
  })
})
