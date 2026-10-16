import type { ReactNode } from "react"
import { beforeEach, describe, expect, test, vi } from "vitest"

import {
  handleCommentsListComments,
  handleCommentsListReactions,
  handleRepositoriesGetIssue,
  handleRepositoriesGetPullRequest,
  handleRepositoriesGetPullRequestFiles,
} from "@/client/msw.gen"
import { issue, pullRequest } from "@/test/fixtures"
import { server } from "@/test/server"
import { render, screen } from "@/test/test-utils"
import CommentsSection from "./CommentsSection"
import IssueDetail from "./IssueDetail"
import PullRequestDetail from "./PullRequestDetail"

vi.mock("@tanstack/react-router", () => ({
  useSearch: () => ({}),
  useParams: () => ({ owner: "owner", repo: "repo", number: "1" }),
  Link: ({ children }: { children: ReactNode }) => <span>{children}</span>,
}))

vi.mock("@/hooks/useAuth", () => ({
  default: () => ({ user: { name: "owner" } }),
}))

vi.mock("@/hooks/useCustomToast", () => ({
  default: () => ({ showErrorToast: vi.fn() }),
}))

const body = "**Description**"
const bodyHtml = "<p><strong>Description</strong></p>"

describe("Markdown descriptions and comments", () => {
  beforeEach(() => {
    server.use(
      handleCommentsListComments({ body: { data: [], count: 0 } }),
      handleCommentsListReactions({ body: { data: [] } }),
      handleRepositoriesGetPullRequestFiles({ body: { files: [], additions: 0, deletions: 0 } }),
      handleRepositoriesGetIssue({ body: { ...issue, body, body_html: bodyHtml } }),
      handleRepositoriesGetPullRequest({ body: { ...pullRequest, body, body_html: bodyHtml } }),
    )
  })

  test.each([
    { name: "issue", Component: IssueDetail, edit: "edit-issue", input: "edit-issue-body" },
    { name: "pull request", Component: PullRequestDetail, edit: "edit-pr", input: "edit-pr-body" },
  ])("displays backend HTML and edits raw Markdown for a $name", async ({ Component, edit, input }) => {
    const { user } = render(<Component />)

    expect((await screen.findByText("Description")).tagName).toBe("STRONG")
    expect(screen.queryByText(body)).not.toBeInTheDocument()

    await user.click(screen.getByTestId(edit))
    expect(screen.getByTestId(input)).toHaveValue(body)
  })

  test("displays backend HTML and edits raw Markdown for comments", async () => {
    server.use(
      handleCommentsListComments({
        body: {
          count: 1,
          data: [
            {
              id: "1",
              author_username: "owner",
              body,
              body_html: bodyHtml,
              created_at: "2026-01-01T00:00:00Z",
              updated_at: "2026-01-01T00:00:00Z",
            },
          ],
        },
      }),
    )
    const { user } = render(<CommentsSection owner="owner" repo="repo" number={1} />)

    expect((await screen.findByText("Description")).tagName).toBe("STRONG")
    expect(screen.queryByText(body)).not.toBeInTheDocument()

    await user.click(screen.getByTestId("edit-comment-1"))
    expect(screen.getByTestId("edit-comment-input-1")).toHaveValue(body)
  })
})
