import userEvent from "@testing-library/user-event"
import type { ReactNode } from "react"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { render, screen } from "@/test/test-utils"
import NewIssueForm from "./NewIssueForm"

const createIssue = vi.hoisted(() => vi.fn())
const navigate = vi.hoisted(() => vi.fn())

vi.mock("@/client", () => ({
  RepositoriesService: { createIssue },
}))

vi.mock("@tanstack/react-router", () => ({
  Link: ({
    children,
    "data-testid": testId,
  }: {
    children: ReactNode
    "data-testid"?: string
  }) => <span data-testid={testId}>{children}</span>,
  useNavigate: () => navigate,
}))

describe("NewIssueForm", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

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
    createIssue.mockResolvedValue({ data: {} })
    render(<NewIssueForm owner="owner" repo="repo" />)

    await user.type(screen.getByTestId("issue-title-input"), "Title")
    await user.type(screen.getByTestId("issue-body-input"), "Body")
    await user.click(screen.getByTestId("submit-issue-btn"))

    expect(createIssue).toHaveBeenCalledWith({
      path: { path: "owner/repo.git" },
      body: { title: "Title", body: "Body" },
    })
    await vi.waitFor(() => expect(navigate).toHaveBeenCalled())
  })
})
