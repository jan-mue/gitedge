import { HttpResponse } from "msw"
import type { ReactNode } from "react"
import { beforeEach, describe, expect, test, vi } from "vitest"
import type { ActivityPublic } from "@/client"
import { handleActivityGetFeed, handleRepositoriesListRepositories } from "@/client/msw.gen"
import { server } from "@/test/server"
import { render, screen, waitFor } from "@/test/test-utils"
import Feed from "./Feed"

vi.mock("@/hooks/useAuth", () => ({ default: () => ({ user: { name: "owner" } }) }))
vi.mock("@/components/Repository/StarButton", () => ({ default: () => null }))
vi.mock("@tanstack/react-router", () => ({
  Link: ({ children }: { children: ReactNode }) => <a href="/">{children}</a>,
}))
const activity = (id: number): ActivityPublic => ({
  id: String(id),
  kind: "issue_open",
  title: `Activity ${id}`,
  actor_username: "owner",
  repo_owner: "owner",
  repo_name: "repo",
  created_at: "2026-01-01T00:00:00Z",
})

describe("Feed loading", () => {
  beforeEach(() => {
    server.use(handleRepositoriesListRepositories({ body: { data: [], count: 0 } }))
  })
  test("paints loading cards immediately without claiming the feed or sidebars are empty", async () => {
    let finish: (value: { data: ActivityPublic[]; count: number }) => void = () => {}
    const response = new Promise<{ data: ActivityPublic[]; count: number }>((resolve) => {
      finish = resolve
    })
    const listRepositories = vi.fn(() => HttpResponse.json({ data: [], count: 0 }))
    server.use(
      handleActivityGetFeed(async () => HttpResponse.json(await response)),
      handleRepositoriesListRepositories(listRepositories),
    )
    render(<Feed />)
    expect(screen.getByRole("status", { name: "Loading feed" })).toBeInTheDocument()
    expect(screen.queryByText(/No activity yet/)).not.toBeInTheDocument()
    expect(screen.queryByText("No repositories yet.")).not.toBeInTheDocument()
    expect(listRepositories).not.toHaveBeenCalled()
    finish({ data: [activity(1)], count: 1 })
    expect(await screen.findByText("Activity 1")).toBeInTheDocument()
    await waitFor(() => expect(listRepositories).toHaveBeenCalledOnce())
    expect(screen.queryByRole("status", { name: "Loading feed" })).not.toBeInTheDocument()
  })
  test("shows a retry state instead of empty activity after a failed request", async () => {
    server.use(handleActivityGetFeed(() => HttpResponse.json({ detail: "Unavailable" }, { status: 503 })))
    const { user } = render(<Feed />)
    expect(await screen.findByText("Unable to load your feed.")).toBeInTheDocument()
    expect(screen.queryByText(/No activity yet/)).not.toBeInTheDocument()
    server.use(handleActivityGetFeed({ body: { data: [activity(2)], count: 1 } }))
    await user.click(screen.getByRole("button", { name: "Try again" }))
    expect(await screen.findByText("Activity 2")).toBeInTheDocument()
  })
  test("loads a small first page and appends more activity on request", async () => {
    const getFeed = vi.fn()
    server.use(
      handleActivityGetFeed(({ request }) => {
        const query = new URL(request.url).searchParams
        getFeed({ limit: Number(query.get("limit")), offset: Number(query.get("offset")) })
        return HttpResponse.json({
          data:
            query.get("offset") === "20"
              ? [activity(21)]
              : Array.from({ length: 20 }, (_, index) => activity(index + 1)),
          count: query.get("offset") === "20" ? 1 : 20,
        })
      }),
    )
    const { user } = render(<Feed />)
    expect(await screen.findByText("Activity 1")).toBeInTheDocument()
    expect(getFeed).toHaveBeenCalledExactlyOnceWith({ limit: 20, offset: 0 })
    await user.click(screen.getByRole("button", { name: "Load more activity" }))
    expect(await screen.findByText("Activity 21")).toBeInTheDocument()
    expect(getFeed).toHaveBeenLastCalledWith({ limit: 20, offset: 20 })
    expect(screen.getAllByRole("article")).toHaveLength(21)
    expect(screen.queryByRole("button", { name: "Load more activity" })).not.toBeInTheDocument()
  })
})
