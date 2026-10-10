import type { ReactNode } from "react"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { render, screen } from "@/test/test-utils"
import PullRequestsList from "./PullRequestsList"

const listPullRequests = vi.hoisted(() => vi.fn())

vi.mock("@/client/sdk.gen", () => ({
  RepositoriesService: { listPullRequests },
}))

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, "data-testid": testId }: { children: ReactNode; "data-testid"?: string }) => (
    <span data-testid={testId}>{children}</span>
  ),
}))

describe("PullRequestsList", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  test("shows the empty state when there are no pull requests", async () => {
    listPullRequests.mockResolvedValue({
      data: { data: [], count: 0, open_count: 0, closed_count: 0 },
    })

    render(<PullRequestsList owner="owner" repo="repo" />)

    expect(await screen.findByTestId("pulls-empty-state")).toBeInTheDocument()
  })

  test("renders pull requests and counts", async () => {
    listPullRequests.mockResolvedValue({
      data: {
        data: [
          {
            id: "1",
            repo_path: "owner/repo.git",
            number: 1,
            title: "First pull request",
            body: null,
            state: "open",
            head_branch: "feature",
            base_branch: "main",
            author_email: null,
            merge_base: null,
            merged_commit_id: null,
            has_merged: false,
            created_at: "2026-01-01T00:00:00Z",
            updated_at: null,
          },
        ],
        count: 1,
        open_count: 1,
        closed_count: 0,
      },
    })

    render(<PullRequestsList owner="owner" repo="repo" />)

    expect(await screen.findByTestId("pr-1")).toHaveTextContent("First pull request")
    expect(screen.getByText("1 Open")).toBeInTheDocument()
    expect(screen.getByTestId("new-pr-btn")).toBeInTheDocument()
  })
})
