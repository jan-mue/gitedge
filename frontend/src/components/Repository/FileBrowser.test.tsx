import type { ComponentProps } from "react"
import { describe, expect, test } from "vitest"
import type { TreeEntry } from "@/client"
import { renderWithRouter, screen, waitFor, within } from "@/test/test-utils"
import FileBrowser from "./FileBrowser"

const timestamp = Math.floor(Date.now() / 1000) - 120
const entries: TreeEntry[] = [
  { name: "src", path: "src", type: "tree" as const, size: null },
  { name: "README.md", path: "README.md", type: "blob" as const, size: 12 },
].map((entry, index) => ({
  ...entry,
  last_commit: {
    sha: (index ? "b" : "a").repeat(40),
    author: "Jan",
    message: `Update ${entry.name}\n\nDetails`,
    timestamp,
  },
}))
const renderBrowser = (props: Partial<ComponentProps<typeof FileBrowser>> = {}) =>
  renderWithRouter({
    initialPath: "/$",
    component: () => <FileBrowser entries={entries} owner="owner" repo="repo" {...props} />,
  })

describe("FileBrowser", () => {
  test("shows separate source and commit links with timestamps instead of file sizes", async () => {
    renderBrowser()
    await screen.findByTestId("file-tree")
    for (const entry of entries) {
      const row = screen.getByTestId(`file-row-${entry.name}`)
      expect(within(row).getByRole("link", { name: entry.name })).toHaveAttribute(
        "href",
        `/owner/repo/src/branch/main/${entry.path}`,
      )
      expect(within(row).getByRole("link", { name: `Update ${entry.name}` })).toHaveAttribute(
        "href",
        `/owner/repo/commit/${entry.last_commit?.sha}`,
      )
      expect(within(row).getByText("2 minutes ago")).toHaveAttribute(
        "dateTime",
        new Date(timestamp * 1000).toISOString(),
      )
      expect(row).not.toHaveTextContent("Details")
      expect(row.querySelector("button, a a")).toBeNull()
    }
    expect(screen.queryByText("12 B")).not.toBeInTheDocument()
  })
  test.each(entries)("opens $name's own commit when its message is clicked", async (entry) => {
    const { user, router } = renderBrowser()
    await user.click(await screen.findByTestId(`entry-commit-${entry.name}`))
    await waitFor(() => expect(router.state.location.pathname).toBe(`/owner/repo/commit/${entry.last_commit?.sha}`))
  })
  test.each(entries)("opens $name's source when its filename is clicked", async (entry) => {
    const { user, router } = renderBrowser()
    await user.click(await screen.findByTestId(`tree-entry-${entry.name}`))
    await waitFor(() => expect(router.state.location.pathname).toBe(`/owner/repo/src/branch/main/${entry.path}`))
  })
  test.each(["branch", "tag", "commit"] as const)("preserves %s source links and full commit URLs", async (mode) => {
    const refName = mode === "commit" ? "c".repeat(40) : "release"
    renderBrowser({ mode, refName })
    await screen.findByTestId("file-tree")
    for (const entry of entries) {
      expect(screen.getByTestId(`tree-entry-${entry.name}`)).toHaveAttribute(
        "href",
        `/owner/repo/src/${mode}/${refName}/${entry.path}`,
      )
      expect(screen.getByTestId(`entry-commit-${entry.name}`)).toHaveAttribute(
        "href",
        `/owner/repo/commit/${entry.last_commit?.sha}`,
      )
    }
  })
  test("supports keyboard navigation between the filename and its commit", async () => {
    const { user, router } = renderBrowser()
    const file = await screen.findByRole("link", { name: "src" })
    file.focus()
    await user.tab()
    expect(screen.getByRole("link", { name: "Update src" })).toHaveFocus()
    await user.keyboard("{Enter}")
    await waitFor(() => expect(router.state.location.pathname).toBe(`/owner/repo/commit/${"a".repeat(40)}`))
  })
  test.each(["src/lib", "src"])("navigates from %s to its parent directory", async (treePath) => {
    const { user, router } = renderBrowser({ treePath })
    await user.click(await screen.findByTestId("tree-entry-parent"))
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(`/owner/repo/src/branch/main${treePath === "src" ? "" : "/src"}`),
    )
  })
  test("does not create a commit link when metadata is missing", async () => {
    renderBrowser({ entries: [{ ...entries[0], last_commit: null }] })
    const row = await screen.findByTestId("file-row-src")
    expect(within(row).getByText("Commit information unavailable")).toBeInTheDocument()
    expect(within(row).getAllByRole("link")).toHaveLength(1)
  })
  test("renders the last commit bar", async () => {
    renderBrowser({
      entries: [],
      lastCommit: {
        sha: "abcdef1234",
        message: "Initial commit",
        author: "Test User",
        timestamp: Math.floor(Date.now() / 1000),
      },
    })
    expect(await screen.findByText("Test User")).toBeInTheDocument()
    expect(screen.getByText("Initial commit")).toBeInTheDocument()
    expect(screen.getByText("just now")).toBeInTheDocument()
  })
  test("shows the empty state when there are no entries", async () => {
    renderBrowser({ entries: [] })
    expect(await screen.findByText("This repository is empty")).toBeInTheDocument()
  })
})
