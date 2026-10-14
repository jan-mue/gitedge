import userEvent from "@testing-library/user-event"
import { HttpResponse } from "msw"
import type { ReactNode } from "react"
import { beforeEach, describe, expect, test, vi } from "vitest"

import {
  handleReleasesListTags,
  handleRepositoriesGetRepositoryInfo,
  handleRepositoriesGetStatistics,
  handleRepositoriesListBranches,
} from "@/client/msw.gen"
import { server } from "@/test/server"
import { render, screen, waitFor } from "@/test/test-utils"
import RepoStats from "./RepoStats"

const navigate = vi.hoisted(() => vi.fn())

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => navigate,
  Link: ({ children, "data-testid": testId }: { children: ReactNode; "data-testid"?: string }) => (
    <a data-testid={testId} href="/">
      {children}
    </a>
  ),
}))

describe("RepoStats", () => {
  beforeEach(() => {
    server.use(
      handleReleasesListTags({
        body: {
          data: [
            { name: "develop", commit_sha: "abc123" },
            { name: "v1.0.0", commit_sha: "def456" },
          ],
          count: 2,
        },
      }),
      handleRepositoriesGetRepositoryInfo({
        body: {
          name: "repo",
          owner: "owner",
          default_branch: "main",
          branch_count: 2,
          tag_count: 1,
          last_commit: {
            sha: "abcdef1234",
            message: "Initial commit",
            author: "Test User",
            timestamp: 1_700_000_000,
          },
        },
      }),
      handleRepositoriesListBranches({
        body: [
          { name: "main", is_default: true },
          { name: "develop", is_default: false },
        ],
      }),
      handleRepositoriesGetStatistics({
        body: { commit_count: 42, size: 2048, languages: [{ name: "Python", percentage: 100, size: 2048 }] },
      }),
    )
  })

  test("renders the clone url and copy button", () => {
    render(<RepoStats owner="owner" repo="repo" gitRef="main" />)

    expect(screen.getByTestId("repo-stats")).toBeInTheDocument()
    expect(screen.getByTestId("clone-url")).toHaveValue(`${window.location.origin}/owner/repo.git`)
    expect(screen.getByTestId("copy-clone-url")).toBeInTheDocument()
  })

  test("renders repository stats", async () => {
    render(<RepoStats owner="owner" repo="repo" gitRef="main" />)

    expect(await screen.findByText("branches")).toBeInTheDocument()
    expect(screen.getByText("tag")).toBeInTheDocument()
    expect(await screen.findByText("42")).toBeInTheDocument()
  })

  test("retains navigation without displaying or requesting statistics in subdirectories", async () => {
    const getStatistics = vi.fn(() => HttpResponse.json({ commit_count: 42, size: 2048, languages: [] }))
    const getRepositoryInfo = vi.fn(() =>
      HttpResponse.json({
        owner: "owner",
        name: "repo",
        default_branch: "main",
        branch_count: 2,
        tag_count: 1,
      }),
    )
    server.use(handleRepositoriesGetStatistics(getStatistics), handleRepositoriesGetRepositoryInfo(getRepositoryInfo))
    const { user } = render(<RepoStats owner="owner" repo="repo" gitRef="main" showStatistics={false} />)
    await waitFor(() => expect(getRepositoryInfo).toHaveBeenCalled())

    expect(getStatistics).not.toHaveBeenCalled()
    expect(screen.queryByText("42")).not.toBeInTheDocument()
    expect(screen.queryByText("branches")).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Python: 100%" })).not.toBeInTheDocument()
    expect(screen.getByTestId("clone-url")).toBeInTheDocument()

    await user.click(screen.getByTestId("branch-selector"))
    expect(await screen.findByTestId("branch-option-develop")).toBeInTheDocument()
  })

  test("expands the language breakdown", async () => {
    server.use(
      handleRepositoriesGetStatistics({
        body: { commit_count: 1, size: 12, languages: [{ name: "Python", percentage: 100, size: 12 }] },
      }),
    )
    const { user } = render(<RepoStats owner="owner" repo="repo" gitRef="main" />)
    await user.click(await screen.findByRole("button", { name: "Python: 100%" }))
    expect(screen.getByText("Python")).toBeInTheDocument()
    expect(screen.getByText("100%")).toBeInTheDocument()
  })

  test("lists branches in the dropdown", async () => {
    const user = userEvent.setup()
    render(<RepoStats owner="owner" repo="repo" gitRef="main" />)

    await user.click(screen.getByTestId("branch-selector"))

    expect(await screen.findByTestId("branch-dropdown")).toBeInTheDocument()
    expect(await screen.findByTestId("branch-option-main")).toBeInTheDocument()
    expect(screen.getByTestId("branch-option-develop")).toBeInTheDocument()
  })

  test("navigates when a branch is selected", async () => {
    const user = userEvent.setup()
    render(<RepoStats owner="owner" repo="repo" gitRef="main" />)

    await user.click(screen.getByTestId("branch-selector"))
    await user.click(await screen.findByTestId("branch-option-develop"))

    expect(navigate).toHaveBeenCalledWith(
      expect.objectContaining({
        to: "/$owner/$repo/src/branch/$branch",
        params: { owner: "owner", repo: "repo", branch: "develop" },
      }),
    )
  })

  test("retries a failed branch request and keeps the picker usable", async () => {
    server.use(handleRepositoriesListBranches(() => new HttpResponse(null, { status: 503 }), { once: true }))
    const { user } = render(<RepoStats owner="owner" repo="repo" gitRef="main" />)
    await user.click(screen.getByRole("button", { name: "Switch branch" }))
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load branches")
    await user.click(screen.getByRole("button", { name: "Try again" }))
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument())
    expect(await screen.findByRole("option", { name: "develop" })).toBeInTheDocument()
  })

  test("searches branches and tags and navigates to the tag namespace", async () => {
    const { user } = render(<RepoStats owner="owner" repo="repo" gitRef="main" />)
    await user.click(screen.getByTestId("branch-selector"))
    const filter = screen.getByRole("textbox", { name: "Filter branch or tag" })
    await user.type(filter, "DEVELOP")
    expect(await screen.findByRole("option", { name: "develop" })).toBeInTheDocument()
    expect(screen.queryByRole("option", { name: "main" })).not.toBeInTheDocument()
    await user.click(screen.getByRole("tab", { name: "Tags" }))
    await user.click(await screen.findByRole("option", { name: "develop" }))
    expect(navigate).toHaveBeenCalledWith({
      to: "/$owner/$repo/src/tag/$tag",
      params: { owner: "owner", repo: "repo", tag: "develop" },
    })
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    expect(screen.getByTestId("branch-selector")).toHaveFocus()
  })
})
