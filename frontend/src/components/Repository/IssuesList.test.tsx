import type { ReactNode } from "react"
import { describe, expect, test, vi } from "vitest"

import { handleRepositoriesListIssues } from "@/client/msw.gen"
import { issue } from "@/test/fixtures"
import { server } from "@/test/server"
import { render, screen } from "@/test/test-utils"
import IssuesList from "./IssuesList"

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, "data-testid": testId }: { children: ReactNode; "data-testid"?: string }) => (
    <span data-testid={testId}>{children}</span>
  ),
}))

describe("IssuesList", () => {
  test("shows the empty state when there are no issues", async () => {
    server.use(handleRepositoriesListIssues({ body: { data: [], count: 0, open_count: 0, closed_count: 0 } }))

    render(<IssuesList owner="owner" repo="repo" />)

    expect(await screen.findByTestId("issues-empty-state")).toBeInTheDocument()
  })

  test("renders issues and counts", async () => {
    server.use(
      handleRepositoriesListIssues({
        body: {
          data: [issue],
          count: 1,
          open_count: 1,
          closed_count: 0,
        },
      }),
    )

    render(<IssuesList owner="owner" repo="repo" />)

    expect(await screen.findByTestId("issue-1")).toHaveTextContent("First issue")
    expect(screen.getByText("1 Open")).toBeInTheDocument()
    expect(screen.getByText("0 Closed")).toBeInTheDocument()
    expect(screen.getByTestId("new-issue-btn")).toBeInTheDocument()
  })
})
