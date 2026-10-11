import type { ReactNode } from "react"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { handleForksListForks, handleStarsGetStarState, handleWatchersGetWatchState } from "@/client/msw.gen"
import { server } from "@/test/server"
import { render, screen, waitFor } from "@/test/test-utils"
import RepoHeader from "./RepoHeader"

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
  beforeEach(() => {
    server.use(
      handleStarsGetStarState({ body: { is_starred: false, stars_count: 2 } }),
      handleWatchersGetWatchState({ body: { is_watching: false, watchers_count: 3 } }),
      handleForksListForks({ body: { data: [], count: 4 } }),
    )
  })

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

  test("renders counts returned by the API", async () => {
    render(<RepoHeader owner="owner" repo="repo" />)

    await waitFor(() => {
      expect(screen.getByTestId("star-count")).toHaveTextContent("2")
      expect(screen.getByTestId("watch-count")).toHaveTextContent("3")
      expect(screen.getByTestId("fork-count")).toHaveTextContent("4")
    })
  })
})
