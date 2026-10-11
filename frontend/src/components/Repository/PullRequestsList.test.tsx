import type { ReactNode } from "react"
import { describe, expect, test, vi } from "vitest"

import { handleRepositoriesListPullRequests } from "@/client/msw.gen"
import { pullRequest } from "@/test/fixtures"
import { server } from "@/test/server"
import { render, screen } from "@/test/test-utils"
import PullRequestsList from "./PullRequestsList"

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, "data-testid": testId }: { children: ReactNode; "data-testid"?: string }) => (
    <span data-testid={testId}>{children}</span>
  ),
}))

describe("PullRequestsList", () => {
  test("shows the empty state when there are no pull requests", async () => {
    server.use(handleRepositoriesListPullRequests({ body: { data: [], count: 0, open_count: 0, closed_count: 0 } }))

    render(<PullRequestsList owner="owner" repo="repo" />)

    expect(await screen.findByTestId("pulls-empty-state")).toBeInTheDocument()
  })

  test("renders pull requests and counts", async () => {
    server.use(
      handleRepositoriesListPullRequests({
        body: {
          data: [pullRequest],
          count: 1,
          open_count: 1,
          closed_count: 0,
        },
      }),
    )

    render(<PullRequestsList owner="owner" repo="repo" />)

    expect(await screen.findByTestId("pr-1")).toHaveTextContent("First pull request")
    expect(screen.getByText("1 Open")).toBeInTheDocument()
    expect(screen.getByTestId("new-pr-btn")).toBeInTheDocument()
  })
})
