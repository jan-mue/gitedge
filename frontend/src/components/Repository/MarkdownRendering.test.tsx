import type { ReactNode } from "react"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { render, screen } from "@/test/test-utils"
import CommentsSection from "./CommentsSection"
import IssueDetail from "./IssueDetail"
import PullRequestDetail from "./PullRequestDetail"

const { getIssue, getPullRequest, getPullRequestFiles, listComments } = vi.hoisted(() => ({
  getIssue: vi.fn(),
  getPullRequest: vi.fn(),
  getPullRequestFiles: vi.fn(),
  listComments: vi.fn(),
}))

vi.mock("@/client", () => ({
  RepositoriesService: { getIssue, getPullRequest, getPullRequestFiles },
  CommentsService: { listComments },
}))

vi.mock("@tanstack/react-router", () => ({
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
    vi.clearAllMocks()
    listComments.mockResolvedValue({ data: { data: [], count: 0 } })
    getPullRequestFiles.mockResolvedValue({ data: { files: [] } })
  })

  test.each([
    { name: "issue", Component: IssueDetail, get: getIssue, edit: "edit-issue", input: "edit-issue-body" },
    { name: "pull request", Component: PullRequestDetail, get: getPullRequest, edit: "edit-pr", input: "edit-pr-body" },
  ])("displays backend HTML and edits raw Markdown for a $name", async ({ Component, get, edit, input }) => {
    get.mockResolvedValue({
      data: {
        title: "Title",
        number: 1,
        state: "open",
        author_username: "owner",
        body,
        body_html: bodyHtml,
        head_branch: "feature",
        base_branch: "main",
      },
    })
    const { user } = render(<Component />)

    expect((await screen.findByText("Description")).tagName).toBe("STRONG")
    expect(screen.queryByText(body)).not.toBeInTheDocument()

    await user.click(screen.getByTestId(edit))
    expect(screen.getByTestId(input)).toHaveValue(body)
  })

  test("displays backend HTML and edits raw Markdown for comments", async () => {
    listComments.mockResolvedValue({
      data: {
        count: 1,
        data: [{ id: "1", author_username: "owner", body, body_html: bodyHtml, created_at: "2026-01-01T00:00:00Z" }],
      },
    })
    const { user } = render(<CommentsSection owner="owner" repo="repo" number={1} />)

    expect((await screen.findByText("Description")).tagName).toBe("STRONG")
    expect(screen.queryByText(body)).not.toBeInTheDocument()

    await user.click(screen.getByTestId("edit-comment-1"))
    expect(screen.getByTestId("edit-comment-input-1")).toHaveValue(body)
  })
})
