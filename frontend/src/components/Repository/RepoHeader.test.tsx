import userEvent from "@testing-library/user-event"
import type { ReactNode } from "react"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { render, screen } from "@/test/test-utils"
import RepoHeader from "./RepoHeader"

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, "data-testid": testId }: { children: ReactNode; "data-testid"?: string }) => (
    <a data-testid={testId} href="/">
      {children}
    </a>
  ),
  useMatches: () => [{ fullPath: "/$owner/$repo/" }],
}))

describe("RepoHeader", () => {
  beforeEach(() => {
    document.documentElement.classList.remove("light", "dark")
  })

  test("renders the header and tabs", () => {
    render(<RepoHeader owner="owner" repo="repo" />)

    expect(screen.getByTestId("repo-header")).toBeInTheDocument()
    expect(screen.getByTestId("tab-code")).toHaveTextContent("Code")
    expect(screen.getByTestId("tab-issues")).toHaveTextContent("Issues")
    expect(screen.getByTestId("tab-pulls")).toHaveTextContent("Pull Requests")
  })

  test("renders the owner and repository name", () => {
    render(<RepoHeader owner="owner" repo="repo" />)

    expect(screen.getByTestId("repo-header")).toHaveTextContent("owner")
    expect(screen.getByTestId("repo-header")).toHaveTextContent("repo")
  })

  test("toggles the theme", async () => {
    const user = userEvent.setup()
    render(<RepoHeader owner="owner" repo="repo" />)

    await user.click(screen.getByTestId("theme-toggle"))

    expect(document.documentElement).toHaveClass("dark")
  })
})
