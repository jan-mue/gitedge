import userEvent from "@testing-library/user-event"
import { HttpResponse } from "msw"
import type { ReactNode } from "react"
import { describe, expect, test, vi } from "vitest"

import { handleRepositoriesCreateIssue } from "@/client/msw.gen"
import { issue } from "@/test/fixtures"
import { server } from "@/test/server"
import { render, screen } from "@/test/test-utils"
import NewIssueForm from "./NewIssueForm"

const navigate = vi.hoisted(() => vi.fn())

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, "data-testid": testId }: { children: ReactNode; "data-testid"?: string }) => (
    <span data-testid={testId}>{children}</span>
  ),
  useNavigate: () => navigate,
}))

describe("NewIssueForm", () => {
  test("disables submit until a title is entered", async () => {
    const user = userEvent.setup()
    render(<NewIssueForm owner="owner" repo="repo" />)

    const submit = screen.getByTestId("submit-issue-btn")
    expect(submit).toBeDisabled()

    await user.type(screen.getByTestId("issue-title-input"), "Title")

    expect(submit).toBeEnabled()
  })

  test("creates an issue and navigates back to the list", async () => {
    const user = userEvent.setup()
    const createIssue = vi.fn()
    server.use(
      handleRepositoriesCreateIssue(async ({ request, params }) => {
        createIssue({ params, body: await request.json() })
        return HttpResponse.json(issue, { status: 201 })
      }),
    )
    render(<NewIssueForm owner="owner" repo="repo" />)

    await user.type(screen.getByTestId("issue-title-input"), "Title")
    await user.type(screen.getByTestId("issue-body-input"), "Body")
    await user.click(screen.getByTestId("submit-issue-btn"))

    await vi.waitFor(() =>
      expect(navigate).toHaveBeenCalledWith({
        to: "/$owner/$repo/issues",
        params: { owner: "owner", repo: "repo" },
      }),
    )
    expect(createIssue).toHaveBeenCalledExactlyOnceWith({
      params: expect.objectContaining({ owner: "owner", repo: "repo" }),
      body: { title: "Title", body: "Body" },
    })
  })
})
