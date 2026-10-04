import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, test, vi } from "vitest"

import type { TreeEntry } from "@/client"
import FileBrowser from "./FileBrowser"

const navigate = vi.hoisted(() => vi.fn())

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => navigate,
}))

const entries: TreeEntry[] = [
  { name: "src", path: "src", type: "tree", size: null },
  { name: "README.md", path: "README.md", type: "blob", size: 12 },
]

describe("FileBrowser", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  test("renders file and directory entries", () => {
    render(<FileBrowser entries={entries} owner="owner" repo="repo" />)

    expect(screen.getByTestId("file-tree")).toBeInTheDocument()
    expect(screen.getByTestId("tree-entry-src")).toBeInTheDocument()
    expect(screen.getByTestId("tree-entry-README.md")).toBeInTheDocument()
  })

  test("navigates into a directory when clicked", async () => {
    const user = userEvent.setup()
    render(<FileBrowser entries={entries} owner="owner" repo="repo" />)

    await user.click(screen.getByTestId("tree-entry-src"))

    expect(navigate).toHaveBeenCalledWith(expect.objectContaining({ search: { ref: undefined, path: "src" } }))
  })

  test("navigates to the blob route for a file", async () => {
    const user = userEvent.setup()
    render(<FileBrowser entries={entries} owner="owner" repo="repo" />)

    await user.click(screen.getByTestId("tree-entry-README.md"))

    expect(navigate).toHaveBeenCalledWith(
      expect.objectContaining({
        search: { ref: undefined, path: "README.md" },
      }),
    )
  })

  test("renders a parent link in a subdirectory", () => {
    render(<FileBrowser entries={entries} owner="owner" repo="repo" treePath="src/lib" />)

    expect(screen.getByTestId("tree-entry-parent")).toBeInTheDocument()
  })

  test("navigates to the parent directory", async () => {
    const user = userEvent.setup()
    render(<FileBrowser entries={entries} owner="owner" repo="repo" treePath="src/lib" />)

    await user.click(screen.getByTestId("tree-entry-parent"))

    expect(navigate).toHaveBeenCalledWith(expect.objectContaining({ search: { ref: undefined, path: "src" } }))
  })

  test("renders the last commit bar", () => {
    render(
      <FileBrowser
        entries={[]}
        owner="owner"
        repo="repo"
        lastCommit={{
          sha: "abcdef1234",
          message: "Initial commit",
          author: "Test User",
          timestamp: Math.floor(Date.now() / 1000),
        }}
      />,
    )

    expect(screen.getByText("Test User")).toBeInTheDocument()
    expect(screen.getByText("Initial commit")).toBeInTheDocument()
    expect(screen.getByText("just now")).toBeInTheDocument()
  })

  test("shows the empty state when there are no entries", () => {
    render(<FileBrowser entries={[]} owner="owner" repo="repo" />)

    expect(screen.getByText("This repository is empty")).toBeInTheDocument()
  })
})
