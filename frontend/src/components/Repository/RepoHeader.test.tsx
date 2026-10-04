import type { ReactNode } from "react"
import { describe, expect, test, vi } from "vitest"

import { render, screen } from "@/test/test-utils"
import RepoHeader from "./RepoHeader"

const { starState, watchState } = vi.hoisted(() => ({
  starState: { data: { is_starred: false, stars_count: 0 } },
  watchState: { data: { is_watching: false, watchers_count: 0 } },
}))

vi.mock("@/client", () => ({
  StarsService: {
    getStarState: vi.fn().mockResolvedValue(starState),
    starRepository: vi.fn().mockResolvedValue(starState),
    unstarRepository: vi.fn().mockResolvedValue(starState),
  },
  WatchersService: {
    getWatchState: vi.fn().mockResolvedValue(watchState),
    watchRepository: vi.fn().mockResolvedValue(watchState),
    unwatchRepository: vi.fn().mockResolvedValue(watchState),
  },
  ForksService: {
    forkRepository: vi.fn(),
    listForks: vi.fn().mockResolvedValue({ data: { data: [], count: 0 } }),
  },
}))

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, "data-testid": testId }: { children: ReactNode; "data-testid"?: string }) => (
    <a data-testid={testId} href="/">
      {children}
    </a>
  ),
  useMatches: () => [{ fullPath: "/$owner/$repo/" }],
  useNavigate: () => vi.fn(),
}))

describe("RepoHeader", () => {
  test("renders the header and tabs", () => {
    render(<RepoHeader owner="owner" repo="repo" />)

    expect(screen.getByTestId("repo-header")).toBeInTheDocument()
    expect(screen.getByTestId("tab-code")).toHaveTextContent("Code")
    expect(screen.getByTestId("tab-issues")).toHaveTextContent("Issues")
    expect(screen.getByTestId("tab-pulls")).toHaveTextContent("Pull requests")
  })

  test("renders the owner and repository name", () => {
    render(<RepoHeader owner="owner" repo="repo" />)

    expect(screen.getByTestId("repo-header")).toHaveTextContent("owner")
    expect(screen.getByTestId("repo-header")).toHaveTextContent("repo")
  })
})
