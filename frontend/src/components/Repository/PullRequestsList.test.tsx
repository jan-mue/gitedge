import type { ReactNode } from "react"
import { describe, expect, test, vi } from "vitest"

import { handleRepositoriesListPullRequests } from "@/client/msw.gen"
import { pullRequest } from "@/test/fixtures"
import { server } from "@/test/server"
import { render, screen } from "@/test/test-utils"
import { PullRequestsList } from "./PullRequestsList"

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

test("combines target branch and author filters, includes merged PRs in closed, and resets", async () => {
  server.use(
    handleRepositoriesListPullRequests({
      body: {
        data: [
          pullRequest,
          {
            ...pullRequest,
            id: "2",
            number: 2,
            title: "Develop feature",
            base_branch: "develop",
            author_username: "alice",
          },
          {
            ...pullRequest,
            id: "3",
            number: 3,
            title: "Merged feature",
            base_branch: "develop",
            author_username: "alice",
            state: "merged",
          },
        ],
        count: 3,
        open_count: 2,
        closed_count: 1,
      },
    }),
  )
  const { user } = render(<PullRequestsList owner="owner" repo="repo" />)
  await screen.findByTestId("pr-1")
  await user.click(screen.getByRole("combobox", { name: "Branch: All target branches" }))
  await user.click(screen.getByRole("option", { name: "develop" }))
  expect(screen.queryByTestId("pr-1")).not.toBeInTheDocument()
  expect(screen.getByTestId("pr-2")).toBeInTheDocument()
  await user.click(screen.getByRole("combobox", { name: "Author: All authors" }))
  await user.click(screen.getByRole("option", { name: "alice" }))
  await user.click(screen.getByRole("button", { name: "1 Closed" }))
  expect(screen.getByTestId("pr-3")).toBeInTheDocument()
  expect(screen.queryByTestId("pr-2")).not.toBeInTheDocument()
  await user.click(screen.getByRole("button", { name: "1 Merged" }))
  expect(screen.getByTestId("pr-3")).toBeInTheDocument()
  await user.click(screen.getByRole("button", { name: "Clear filters" }))
  expect(screen.getByTestId("pr-1")).toBeInTheDocument()
  expect(screen.getByTestId("pr-2")).toBeInTheDocument()
  expect(screen.queryByTestId("pr-3")).not.toBeInTheDocument()
  expect(screen.getByRole("combobox", { name: "Branch: All target branches" })).toBeInTheDocument()
})
