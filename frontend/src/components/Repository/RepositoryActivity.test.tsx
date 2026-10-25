import { HttpResponse } from "msw"
import type { ReactNode } from "react"
import { beforeEach, describe, expect, test, vi } from "vitest"

import type { RepositoryActivityStatistics } from "@/client"
import { handleActivityGetRepositoryActivityStatistics } from "@/client/msw.gen"
import { server } from "@/test/server"
import { render, screen, waitFor } from "@/test/test-utils"
import { RepositoryActivity } from "./RepositoryActivity"

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, to, params }: { children: ReactNode; to: string; params: Record<string, string> }) => (
    <a href={to.replace(/\$(\w+)/g, (_, key: string) => params[key])}>{children}</a>
  ),
}))
vi.mock("./ActivityChart", () => ({
  ActivityChart: ({ label, metric = "commits" }: { label: string; metric?: string }) => (
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
  recent_commits: [{ date: "2026-10-05", commits: 8, additions: 0, deletions: 0 }],
}

describe("RepositoryActivity", () => {
  beforeEach(() => {
    server.use(handleActivityGetRepositoryActivityStatistics({ body: statistics }))
  })

  test("renders pulse and fetches a new period with changed totals", async () => {
    const getStatistics = vi.fn()
    server.use(
      handleActivityGetRepositoryActivityStatistics(({ request, params }) => {
        const days = Number(new URL(request.url).searchParams.get("days"))
        getStatistics({ params, days })
        return HttpResponse.json({
          ...statistics,
          overview: { ...statistics.overview, additions: days === 1 ? 25 : 120 },
        })
      }),
    )
    const { user } = render(<RepositoryActivity owner="owner" repo="repo" />)
    expect(await screen.findByText("Overview")).toBeInTheDocument()
    expect(getStatistics).toHaveBeenCalledExactlyOnceWith({
      params: expect.objectContaining({ owner: "owner", repo: "repo" }),
      days: 7,
    })
    expect(screen.getByText("Improve activity")).toHaveAttribute("href", "/owner/repo/pulls/17")
    expect(screen.getByText("120 additions")).toBeInTheDocument()
    await user.click(screen.getByRole("combobox", { name: "Activity period" }))
    expect(screen.getAllByRole("option").map((option) => option.textContent)).toEqual([
      "1 day",
      "3 days",
      "1 week",
      "1 month",
      "3 months",
      "6 months",
      "1 year",
    ])
    await user.click(screen.getByRole("option", { name: "1 day" }))
    await waitFor(() =>
      expect(getStatistics).toHaveBeenLastCalledWith({
        params: expect.objectContaining({ owner: "owner", repo: "repo" }),
        days: 1,
      }),
    )
    expect(await screen.findByText("25 additions")).toBeInTheDocument()
    for (const days of [90, 180, 365]) {
      await user.click(screen.getByRole("combobox", { name: "Activity period" }))
      await user.click(
        screen.getByRole("option", {
          name: ({ 90: "3 months", 180: "6 months", 365: "1 year" } as Record<number, string>)[days],
        }),
      )
      await waitFor(() =>
        expect(getStatistics).toHaveBeenLastCalledWith({
          params: expect.objectContaining({ owner: "owner", repo: "repo" }),
          days,
        }),
      )
      expect(await screen.findByLabelText("Activity period")).toHaveTextContent(
        ({ 90: "3 months", 180: "6 months", 365: "1 year" } as Record<number, string>)[days],
      )
    }
  }, 15_000)

  test("switches views, ranks by selected metric, and shows the past-year commit chart", async () => {
    const getStatistics = vi.fn(() => HttpResponse.json(statistics))
    server.use(handleActivityGetRepositoryActivityStatistics(getStatistics))
    const { user } = render(<RepositoryActivity owner="owner" repo="repo" />)
    await screen.findByText("Overview")
    await user.click(screen.getByRole("button", { name: "Contributors" }))
    expect(screen.getAllByTestId("activity-contributor")[0]).toHaveTextContent("Alice")
    await user.click(screen.getByRole("combobox", { name: "Contribution metric" }))
    await user.click(screen.getByRole("option", { name: "Additions" }))
    expect(screen.getAllByTestId("activity-contributor")[0]).toHaveTextContent("Bob")
    expect(screen.getByLabelText("Overall additions")).toHaveAttribute("data-metric", "additions")
    await user.click(screen.getByRole("button", { name: "Code frequency" }))
    expect(screen.getByLabelText("Weekly additions and deletions")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Recent commits" }))
    expect(screen.getByText("Number of commits in the past year")).toBeInTheDocument()
    expect(screen.getByLabelText("Weekly commits in the past year")).toHaveAttribute("data-metric", "commits")
    expect(screen.getByRole("button", { name: "Recent commits" })).toHaveAttribute("aria-pressed", "true")
    expect(getStatistics).toHaveBeenCalledTimes(1)
  })

  test("shows loading, error, and retry states", async () => {
    server.use(
      handleActivityGetRepositoryActivityStatistics(() => new HttpResponse(null, { status: 503 }), { once: true }),
    )
    const { user } = render(<RepositoryActivity owner="owner" repo="repo" />)
    expect(screen.getByRole("status")).toHaveTextContent("Loading activity")
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load repository activity")
    await user.click(screen.getByRole("button", { name: "Try again" }))
    expect(await screen.findByText("Overview")).toBeInTheDocument()
  })

  test("matches the selected activity view while statistics are loading", async () => {
    let finish: (value: RepositoryActivityStatistics) => void = () => {}
    const response = new Promise<RepositoryActivityStatistics>((resolve) => {
      finish = resolve
    })
    server.use(handleActivityGetRepositoryActivityStatistics(async () => HttpResponse.json(await response)))
    const { user } = render(<RepositoryActivity owner="owner" repo="repo" />)
    expect(screen.getByRole("status")).toHaveAttribute("data-loading-view", "pulse")
    for (const [label, view] of [
      ["Contributors", "contributors"],
      ["Code frequency", "code-frequency"],
      ["Recent commits", "recent-commits"],
    ]) {
      await user.click(screen.getByRole("button", { name: label }))
      expect(screen.getByRole("status")).toHaveAttribute("data-loading-view", view)
    }
    expect(screen.queryByText("No contributions yet.")).not.toBeInTheDocument()
    finish(statistics)
    expect(await screen.findByText("Number of commits in the past year")).toBeInTheDocument()
    expect(screen.queryByRole("status")).not.toBeInTheDocument()
  })

  test("renders empty states without fabricated activity", async () => {
    server.use(
      handleActivityGetRepositoryActivityStatistics({
        body: { ...statistics, merged_prs: [], contributors: [], code_frequency: [], recent_commits: [] },
      }),
    )
    const { user } = render(<RepositoryActivity owner="owner" repo="repo" />)
    expect(await screen.findByText("No pull requests were merged during this period.")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Contributors" }))
    expect(screen.getByText("No contributions yet.")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Code frequency" }))
    expect(screen.getByText("No code changes yet.")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Recent commits" }))
    expect(screen.getByLabelText("Weekly commits in the past year")).toBeInTheDocument()
  })
})
