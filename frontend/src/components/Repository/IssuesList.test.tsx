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

test("combines status, author and search filters and resets to open issues", async () => {
  server.use(
    handleRepositoriesListIssues({
      body: {
        data: [
          issue,
          { ...issue, id: "2", number: 2, title: "Keyboard navigation", author_username: "alice" },
          { ...issue, id: "3", number: 3, title: "Closed issue", state: "closed", author_username: "alice" },
        ],
        count: 3,
        open_count: 2,
        closed_count: 1,
      },
    }),
  )
  const { user } = render(<IssuesList owner="owner" repo="repo" />)
  await screen.findByTestId("issue-1")
  expect(screen.queryByTestId("issue-3")).not.toBeInTheDocument()
  await user.click(screen.getByRole("combobox", { name: "Author: All authors" }))
  await user.click(screen.getByRole("option", { name: "alice" }))
  expect(screen.queryByTestId("issue-1")).not.toBeInTheDocument()
  expect(screen.getByTestId("issue-2")).toBeInTheDocument()
  await user.type(screen.getByRole("searchbox"), "#3")
  expect(screen.getByText("No matching issues")).toBeInTheDocument()
  await user.click(screen.getByRole("button", { name: "1 Closed" }))
  expect(screen.getByTestId("issue-3")).toBeInTheDocument()
  await user.click(screen.getByRole("button", { name: "Clear filters" }))
  expect(screen.getByRole("searchbox")).toHaveValue("")
  expect(screen.getByTestId("issue-1")).toBeInTheDocument()
  expect(screen.getByTestId("issue-2")).toBeInTheDocument()
  expect(screen.queryByTestId("issue-3")).not.toBeInTheDocument()
})

test("sorts by creation and update timestamps rather than issue number", async () => {
  server.use(
    handleRepositoriesListIssues({
      body: {
        data: [
          { ...issue, updated_at: "2026-10-12T12:00:00Z" },
          { ...issue, id: "2", number: 2, created_at: "2025-01-01T00:00:00Z", updated_at: "2026-01-02T00:00:00Z" },
        ],
        count: 2,
        open_count: 2,
        closed_count: 0,
      },
    }),
  )
  const { user } = render(<IssuesList owner="owner" repo="repo" />)
  await screen.findByTestId("issue-1")
  const rows = () => screen.getAllByTestId(/^issue-\d/).map((row) => row.getAttribute("data-testid"))
  expect(rows()).toEqual(["issue-1", "issue-2"])
  await user.click(screen.getByRole("combobox", { name: "Sort: Newest" }))
  await user.click(screen.getByRole("option", { name: "Oldest" }))
  expect(rows()).toEqual(["issue-2", "issue-1"])
  await user.click(screen.getByRole("combobox", { name: "Sort: Oldest" }))
  await user.click(screen.getByRole("option", { name: "Recently updated" }))
  expect(rows()).toEqual(["issue-1", "issue-2"])
  await user.click(screen.getByRole("combobox", { name: "Sort: Recently updated" }))
  await user.click(screen.getByRole("option", { name: "Least recently updated" }))
  expect(rows()).toEqual(["issue-2", "issue-1"])
})
