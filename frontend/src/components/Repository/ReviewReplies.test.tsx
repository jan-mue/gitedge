import { useQuery } from "@tanstack/react-query"
import { HttpResponse } from "msw"
import { describe, expect, test } from "vitest"
import type { ReviewPublic } from "@/client"
import { reviewsListReviewsOptions } from "@/client/@tanstack/react-query.gen"
import { handleReviewsListReviews, handleReviewsReplyToReview } from "@/client/msw.gen"
import { server } from "@/test/server"
import { render, screen, waitFor } from "@/test/test-utils"
import { ReviewReplies } from "./ReviewReplies"

const review: ReviewPublic = {
  id: "review-1",
  author_username: "bob",
  state: "comment",
  body: "Summary",
  base_commit: "a".repeat(40),
  head_commit: "b".repeat(40),
  created_at: "2026-10-16T00:00:00Z",
  replies: [],
}
const Thread = () => {
  const { data } = useQuery(reviewsListReviewsOptions({ path: { owner: "owner", repo: "repo", number: 1 } }))
  return data ? (
    <ReviewReplies owner="owner" repo="repo" number={1} review={data[0]} commentIndex={0} username="alice" />
  ) : null
}

describe("review replies", () => {
  test("posts to the anchored comment, preserves text on failure, and renders the published reply", async () => {
    let published = review
    let failed = true
    server.use(
      handleReviewsListReviews(() => HttpResponse.json([published])),
      handleReviewsReplyToReview(async ({ request }) => {
        if (failed) return new HttpResponse(null, { status: 503 })
        const body = (await request.json()) as { body: string; comment_index: number }
        expect(body).toEqual({ body: "Thanks for the review", comment_index: 0 })
        const reply = {
          id: "reply-1",
          author_username: "alice",
          created_at: "2026-10-16T12:00:00Z",
          ...body,
          body_html: "<p>Thanks for the <strong>review</strong></p>",
        }
        published = { ...review, replies: [reply] }
        return HttpResponse.json(reply, { status: 201 })
      }),
    )
    const { user } = render(<Thread />)
    await user.click(await screen.findByRole("button", { name: "Reply" }))
    await user.type(screen.getByRole("textbox", { name: "Reply to review comment" }), "Thanks for the review")
    await user.click(screen.getByRole("button", { name: "Reply" }))
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to post your reply")
    expect(screen.getByRole("textbox", { name: "Reply to review comment" })).toHaveValue("Thanks for the review")
    failed = false
    await user.click(screen.getByRole("button", { name: "Reply" }))
    expect(await screen.findByTestId("review-reply-reply-1")).toHaveTextContent("Thanks for the review")
    expect(screen.getByTestId("review-reply-reply-1").querySelector("strong")).toHaveTextContent("alice")
    await waitFor(() => expect(screen.queryByRole("textbox")).not.toBeInTheDocument())
  })

  test("shows sign-in instead of a reply form to anonymous readers", () => {
    render(<ReviewReplies owner="owner" repo="repo" number={1} review={review} />)
    expect(screen.getByRole("link", { name: "Sign in to reply" })).toHaveAttribute("href", "/login")
    expect(screen.queryByRole("button", { name: "Reply" })).not.toBeInTheDocument()
  })
})
