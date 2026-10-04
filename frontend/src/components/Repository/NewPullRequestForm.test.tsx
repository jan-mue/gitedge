import userEvent from "@testing-library/user-event"
import type { ReactNode } from "react"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { render, screen, within } from "@/test/test-utils"
import NewPullRequestForm from "./NewPullRequestForm"

const listBranches = vi.hoisted(() => vi.fn())
const createPullRequest = vi.hoisted(() => vi.fn())
const navigate = vi.hoisted(() => vi.fn())

vi.mock("@/client", () => ({
  RepositoriesService: { listBranches, createPullRequest },
}))

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, "data-testid": testId }: { children: ReactNode; "data-testid"?: string }) => (
    <span data-testid={testId}>{children}</span>
  ),
  useNavigate: () => navigate,
}))

describe("NewPullRequestForm", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listBranches.mockResolvedValue({
      data: [
        { name: "main", is_default: true },
        { name: "feature", is_default: false },
      ],
    })
  })

  test("disables submit until a title and head branch are set", async () => {
    const user = userEvent.setup()
    render(<NewPullRequestForm owner="owner" repo="repo" />)

    const submit = screen.getByTestId("submit-pr-btn")
    expect(submit).toBeDisabled()

    const sourceSelect = screen.getByTestId("pr-source-branch")
    await user.type(screen.getByTestId("pr-title-input"), "Title")
    await within(sourceSelect).findByRole("option", { name: "feature" })
    await user.selectOptions(sourceSelect, "feature")

    expect(submit).toBeEnabled()
  })

  test("creates a pull request and navigates back to the list", async () => {
    const user = userEvent.setup()
    createPullRequest.mockResolvedValue({ data: {} })
    render(<NewPullRequestForm owner="owner" repo="repo" />)

    const sourceSelect = screen.getByTestId("pr-source-branch")
    await user.type(screen.getByTestId("pr-title-input"), "Title")
    await within(sourceSelect).findByRole("option", { name: "feature" })
    await user.selectOptions(sourceSelect, "feature")
    await user.click(screen.getByTestId("submit-pr-btn"))

    expect(createPullRequest).toHaveBeenCalledWith({
      path: { path: "owner/repo.git" },
      body: {
        title: "Title",
        body: null,
        head_branch: "feature",
        base_branch: "main",
      },
    })
    await vi.waitFor(() => expect(navigate).toHaveBeenCalled())
  })
})
