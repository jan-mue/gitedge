import type { ReactNode } from "react"
import { beforeEach, describe, expect, test, vi } from "vitest"
import { render, screen, waitFor } from "@/test/test-utils"
import Feed from "./Feed"

const { getFeed, listRepositories } = vi.hoisted(() => ({ getFeed: vi.fn(), listRepositories: vi.fn() }))
vi.mock("@/client/sdk.gen", () => ({ ActivityService: { getFeed }, RepositoriesService: { listRepositories } }))
vi.mock("@/hooks/useAuth", () => ({ default: () => ({ user: { name: "owner" } }) }))
vi.mock("@/components/Repository/StarButton", () => ({ default: () => null }))
vi.mock("@tanstack/react-router", () => ({
  Link: ({ children }: { children: ReactNode }) => <a href="/">{children}</a>,
}))
const activity = (id: number) => ({
  id: String(id),
  kind: "issue_open",
  title: `Activity ${id}`,
  actor_username: "owner",
  repo_owner: "owner",
  repo_name: "repo",
})

describe("Feed loading", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listRepositories.mockResolvedValue({ data: { data: [], count: 0 } })
  })
  test("paints loading cards immediately without claiming the feed or sidebars are empty", async () => {
    let finish: (value: { data: { data: ReturnType<typeof activity>[]; count: number } }) => void = () => {}
    getFeed.mockReturnValue(
      new Promise((resolve) => {
        finish = resolve
      }),
    )
    render(<Feed />)
    expect(screen.getByRole("status", { name: "Loading feed" })).toBeInTheDocument()
    expect(screen.queryByText(/No activity yet/)).not.toBeInTheDocument()
    expect(screen.queryByText("No repositories yet.")).not.toBeInTheDocument()
    expect(listRepositories).not.toHaveBeenCalled()
    finish({ data: { data: [activity(1)], count: 1 } })
    expect(await screen.findByText("Activity 1")).toBeInTheDocument()
    await waitFor(() => expect(listRepositories).toHaveBeenCalledOnce())
    expect(screen.queryByRole("status", { name: "Loading feed" })).not.toBeInTheDocument()
  })
  test("shows a retry state instead of empty activity after a failed request", async () => {
    getFeed.mockRejectedValue({ detail: "Unavailable" })
    const { user } = render(<Feed />)
    expect(await screen.findByText("Unable to load your feed.")).toBeInTheDocument()
    expect(screen.queryByText(/No activity yet/)).not.toBeInTheDocument()
    getFeed.mockResolvedValue({ data: { data: [activity(2)], count: 1 } })
    await user.click(screen.getByRole("button", { name: "Try again" }))
    expect(await screen.findByText("Activity 2")).toBeInTheDocument()
  })
  test("loads a small first page and appends more activity on request", async () => {
    getFeed.mockImplementation(({ query }) =>
      Promise.resolve({
        data: {
          data: query.offset === 20 ? [activity(21)] : Array.from({ length: 20 }, (_, index) => activity(index + 1)),
          count: query.offset === 20 ? 1 : 20,
        },
      }),
    )
    const { user } = render(<Feed />)
    expect(await screen.findByText("Activity 1")).toBeInTheDocument()
    expect(getFeed.mock.calls[0][0].query.limit).toBe(20)
    await user.click(screen.getByRole("button", { name: "Load more activity" }))
    expect(await screen.findByText("Activity 21")).toBeInTheDocument()
    expect(screen.getAllByRole("article")).toHaveLength(21)
    expect(screen.queryByRole("button", { name: "Load more activity" })).not.toBeInTheDocument()
  })
})
