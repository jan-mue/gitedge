import type { ReactNode } from "react"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { render, screen } from "@/test/test-utils"
import IssuesList from "./IssuesList"

const listIssues = vi.hoisted(() => vi.fn())

vi.mock("@/client", () => ({
  RepositoriesService: { listIssues },
}))

vi.mock("@tanstack/react-router", () => ({
  Link: ({
    children,
    "data-testid": testId,
  }: {
    children: ReactNode
    "data-testid"?: string
  }) => <span data-testid={testId}>{children}</span>,
}))

describe("IssuesList", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  test("shows the empty state when there are no issues", async () => {
    listIssues.mockResolvedValue({
      data: { data: [], count: 0, open_count: 0, closed_count: 0 },
    })

    render(<IssuesList owner="owner" repo="repo" />)

    expect(await screen.findByTestId("issues-empty-state")).toBeInTheDocument()
  })

  test("renders issues and counts", async () => {
    listIssues.mockResolvedValue({
      data: {
        data: [
          {
            id: "1",
            repo_path: "owner/repo.git",
            number: 1,
            title: "First issue",
            body: null,
            state: "open",
            author_email: null,
            created_at: "2026-01-01T00:00:00Z",
            updated_at: null,
          },
        ],
        count: 1,
        open_count: 1,
        closed_count: 0,
      },
    })

    render(<IssuesList owner="owner" repo="repo" />)

    expect(await screen.findByTestId("issue-1")).toHaveTextContent(
      "First issue",
    )
    expect(screen.getByText("1 Open")).toBeInTheDocument()
    expect(screen.getByText("0 Closed")).toBeInTheDocument()
    expect(screen.getByTestId("new-issue-btn")).toBeInTheDocument()
  })
})
