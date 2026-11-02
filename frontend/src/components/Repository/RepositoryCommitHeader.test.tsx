import { describe, expect, test } from "vitest"
import type { CommitInfo, FileContent } from "@/client"
import CodeViewer from "@/components/Repositories/CodeViewer"
import { renderWithRouter, screen, within } from "@/test/test-utils"
import FileBrowser from "./FileBrowser"

const commit: CommitInfo = {
  sha: "abcdef1234567890",
  author: "Jan",
  message: "Fix repository browsing\n\nKeep commit links accessible.",
  timestamp: 1791663993,
}
const file: FileContent = {
  name: "README.md",
  path: "README.md",
  size: 5,
  content: "Hello",
  highlighted_html: "<pre>Hello</pre>",
  css: "",
  css_dark: "",
  language: "text",
  line_count: 1,
}

describe("Source commit links", () => {
  test("links the directory header message and abbreviated SHA to the full commit", async () => {
    renderWithRouter({
      component: () => <FileBrowser owner="owner" repo="repo" entries={[]} lastCommit={commit} />,
    })
    const message = await screen.findByRole("link", { name: "Fix repository browsing" })
    expect(message).toHaveAttribute("href", `/owner/repo/commit/${commit.sha}`)
    expect(message).toHaveAttribute("title", commit.message)
    expect(screen.getByRole("link", { name: "abcdef1234" })).toHaveAttribute("href", message.getAttribute("href"))
  })

  test("renders the same clickable commit header above the file content", async () => {
    renderWithRouter({
      component: () => (
        <CodeViewer
          file={file}
          lastCommit={commit}
          backLink={{ owner: "owner", repo: "repo", mode: "branch", refName: "main", path: "" }}
        />
      ),
    })
    const viewer = await screen.findByTestId("file-viewer")
    const header = within(viewer).getByTestId("last-commit-header")
    expect(within(header).getByRole("link", { name: "Fix repository browsing" })).toHaveAttribute(
      "href",
      `/owner/repo/commit/${commit.sha}`,
    )
    expect(header.compareDocumentPosition(within(viewer).getByTestId("highlighted-content"))).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    )
  })
})
