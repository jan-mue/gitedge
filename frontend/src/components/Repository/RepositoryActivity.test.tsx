import type { ReactNode } from "react"
import { beforeEach, describe, expect, test, vi } from "vitest"

import type { RepositoryActivityStatistics } from "@/client"
import { render, screen, waitFor } from "@/test/test-utils"
import RepositoryActivity from "./RepositoryActivity"

const getStatistics = vi.hoisted(() => vi.fn())

vi.mock("@/client/sdk.gen", () => ({ ActivityService: { getRepositoryActivityStatistics: getStatistics } }))
vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, to, params }: { children: ReactNode; to: string; params: Record<string, string> }) => (
    <a href={to.replace(/\$(\w+)/g, (_, key: string) => params[key])}>{children}</a>
  ),
}))
vi.mock("./ActivityChart", () => ({
  default: ({ label, metric = "commits" }: { label: string; metric?: string }) => (
    <fieldset aria-label={label} data-metric={metric} />
  ),
}))

const statistics: RepositoryActivityStatistics = {
  start: "2026-10-03T12:00:00Z",
  end: "2026-10-10T12:00:00Z",
  default_branch: "develop",
  overview: {
    active_prs: 3,
    active_issues: 2,
    merged_prs: 2,
    proposed_prs: 1,
    closed_issues: 1,
    new_issues: 1,
    merge_authors: 1,
    authors: 2,
    commits: 4,
    branch_commits: 6,
    files_changed: 3,
    additions: 120,
    deletions: 40,
  },
  daily_commits: [{ date: "2026-10-10", commits: 4, additions: 120, deletions: 40 }],
  merged_prs: [
    {
      id: "merge-1",
      kind: "pull_request_merge",
      actor_username: "alice",
      repo_owner: "owner",
      repo_name: "repo",
      target_type: "pull_request",
      target_number: 17,
      title: "Improve activity",
      created_at: "2026-10-10T11:00:00Z",
    },
  ],
  contributors: [
    { name: "Alice", commits: 4, additions: 20, deletions: 10, series: [] },
    { name: "Bob", commits: 2, additions: 100, deletions: 30, series: [] },
  ],
  code_frequency: [{ date: "2026-10-05", commits: 6, additions: 120, deletions: 40 }],
  recent_commits: [
    {
      sha: "a".repeat(40),
      author: "Alice",
      author_email: "alice@example.com",
      message: "Implement activity\n\nDetails",
      timestamp: 1791630000,
    },
  ],
}

describe("RepositoryActivity", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getStatistics.mockResolvedValue({ data: statistics })
  })

  test("renders pulse and fetches a new period with changed totals", async () => {
    const { user } = render(<RepositoryActivity owner="owner" repo="repo" />)
    expect(await screen.findByText("Overview")).toBeInTheDocument()
    expect(screen.getByText("Improve activity")).toHaveAttribute("href", "/owner/repo/pulls/17")
    expect(screen.getByText("120 additions")).toBeInTheDocument()
    getStatistics.mockResolvedValue({ data: { ...statistics, overview: { ...statistics.overview, additions: 25 } } })
    await user.selectOptions(screen.getByLabelText("Activity period"), "1")
    await waitFor(() =>
      expect(getStatistics).toHaveBeenLastCalledWith(
        expect.objectContaining({ path: { owner: "owner", repo: "repo" }, query: { days: 1 } }),
      ),
    )
    expect(await screen.findByText("25 additions")).toBeInTheDocument()
  })

  test("switches views, ranks by selected metric, and links to real commit routes", async () => {
    const { user } = render(<RepositoryActivity owner="owner" repo="repo" />)
    await screen.findByText("Overview")
    await user.click(screen.getByRole("button", { name: "Contributors" }))
    expect(screen.getAllByTestId("activity-contributor")[0]).toHaveTextContent("Alice")
    await user.selectOptions(screen.getByLabelText("Contribution metric"), "additions")
    expect(screen.getAllByTestId("activity-contributor")[0]).toHaveTextContent("Bob")
    expect(screen.getByLabelText("Overall additions")).toHaveAttribute("data-metric", "additions")
    await user.click(screen.getByRole("button", { name: "Code frequency" }))
    expect(screen.getByLabelText("Weekly additions and deletions")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Recent commits" }))
    expect(screen.getByText("Implement activity")).toHaveAttribute("href", `/owner/repo/commit/${"a".repeat(40)}`)
    expect(screen.getByRole("button", { name: "Recent commits" })).toHaveAttribute("aria-pressed", "true")
    expect(getStatistics).toHaveBeenCalledTimes(1)
  })

  test("shows loading, error, and retry states", async () => {
    getStatistics.mockRejectedValueOnce(new Error("Unavailable"))
    const { user } = render(<RepositoryActivity owner="owner" repo="repo" />)
    expect(screen.getByRole("status")).toHaveTextContent("Loading activity")
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load repository activity")
    await user.click(screen.getByRole("button", { name: "Try again" }))
    expect(await screen.findByText("Overview")).toBeInTheDocument()
  })

  test("renders empty states without fabricated activity", async () => {
    getStatistics.mockResolvedValue({
      data: { ...statistics, merged_prs: [], contributors: [], code_frequency: [], recent_commits: [] },
    })
    const { user } = render(<RepositoryActivity owner="owner" repo="repo" />)
    expect(await screen.findByText("No pull requests were merged during this period.")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Contributors" }))
    expect(screen.getByText("No contributions yet.")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Code frequency" }))
    expect(screen.getByText("No code changes yet.")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Recent commits" }))
    expect(screen.getByText("No commits yet.")).toBeInTheDocument()
  })
})
