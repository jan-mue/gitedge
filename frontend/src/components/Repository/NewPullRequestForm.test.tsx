import userEvent from "@testing-library/user-event"
import { HttpResponse } from "msw"
import type { ReactNode } from "react"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { handleRepositoriesCreatePullRequest, handleRepositoriesListBranches } from "@/client/msw.gen"
import { branches, pullRequest } from "@/test/fixtures"
import { server } from "@/test/server"
import { render, screen } from "@/test/test-utils"
import NewPullRequestForm from "./NewPullRequestForm"

const navigate = vi.hoisted(() => vi.fn())

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, "data-testid": testId }: { children: ReactNode; "data-testid"?: string }) => (
    <span data-testid={testId}>{children}</span>
  ),
  useNavigate: () => navigate,
}))

describe("NewPullRequestForm", () => {
  beforeEach(() => {
    server.use(handleRepositoriesListBranches({ body: branches }))
  })

  test("disables submit until a title and head branch are set", async () => {
    const user = userEvent.setup()
    render(<NewPullRequestForm owner="owner" repo="repo" />)

    const submit = screen.getByTestId("submit-pr-btn")
    expect(submit).toBeDisabled()

    const sourceSelect = screen.getByTestId("pr-source-branch")
    await user.type(screen.getByTestId("pr-title-input"), "Title")
    await user.click(sourceSelect)
    await user.click(await screen.findByRole("option", { name: "feature" }))

    expect(submit).toBeEnabled()
  })

  test("creates a pull request and navigates back to the list", async () => {
    const user = userEvent.setup()
    const createPullRequest = vi.fn()
    server.use(
      handleRepositoriesCreatePullRequest(async ({ request, params }) => {
        createPullRequest({ params, body: await request.json() })
        return HttpResponse.json(pullRequest, { status: 201 })
      }),
    )
    render(<NewPullRequestForm owner="owner" repo="repo" />)

    const sourceSelect = screen.getByTestId("pr-source-branch")
    await user.type(screen.getByTestId("pr-title-input"), "Title")
    await user.click(sourceSelect)
    await user.click(await screen.findByRole("option", { name: "feature" }))
    await user.click(screen.getByTestId("submit-pr-btn"))

    await vi.waitFor(() =>
      expect(navigate).toHaveBeenCalledWith({
        to: "/$owner/$repo/pulls",
        params: { owner: "owner", repo: "repo" },
      }),
    )
    expect(createPullRequest).toHaveBeenCalledExactlyOnceWith({
      params: expect.objectContaining({ owner: "owner", repo: "repo" }),
      body: {
        title: "Title",
        body: null,
        head_branch: "feature",
        base_branch: "main",
      },
    })
  })
})
