import type { ReactNode } from "react"
import { describe, expect, test, vi } from "vitest"
import type { FileContent } from "@/client"
import { render, screen } from "@/test/test-utils"
import CodeViewer from "./CodeViewer"

vi.mock("@tanstack/react-router", () => ({
  Link: ({
    children,
    params,
    "data-testid": testId,
  }: {
    children: ReactNode
    params?: { owner: string; repo: string; hash?: string; sha?: string }
    "data-testid"?: string
  }) => (
    <a
      href={params?.hash ? `/${params.owner}/${params.repo}/commit/${params.hash}` : "/"}
      data-testid={testId}
      data-revision={params?.sha}
    >
      {children}
    </a>
  ),
}))

const file: FileContent = {
  name: "main.py",
  path: "src/main.py",
  size: 10,
  content: "print(42)",
  highlighted_html: "<pre>print(42)</pre>",
  css: "",
  css_dark: "",
  language: "Python",
  line_count: 1,
  last_commit: { sha: "a".repeat(40), author: "Jan", message: "Change this file", timestamp: 1_700_000_000 },
}
const backLink = { owner: "owner", repo: "repo", mode: "branch" as const, refName: "main", path: "src" }

describe("CodeViewer", () => {
  test("shows the file's last change above its contents while permalinks use the viewed revision", () => {
    render(
      <CodeViewer
        file={file}
        backLink={backLink}
        commitSha={"b".repeat(40)}
        lastCommit={{
          sha: "b".repeat(40),
          author: "Other author",
          message: "Repository tip",
          timestamp: 1_700_000_001,
        }}
      />,
    )
    const header = screen.getByTestId("last-commit-header")
    expect(header).toHaveTextContent("Jan")
    expect(header).toHaveTextContent("Change this file")
    expect(header).not.toHaveTextContent("Repository tip")
    expect(screen.getByTestId("last-commit-sha")).toHaveAttribute("href", `/owner/repo/commit/${"a".repeat(40)}`)
    expect(
      header.compareDocumentPosition(screen.getByTestId("file-name")) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
    expect(screen.getByText("Permalink")).toHaveAttribute("data-revision", "b".repeat(40))
    expect(screen.getByTestId("highlighted-content")).toHaveTextContent("print(42)")
  })
})
