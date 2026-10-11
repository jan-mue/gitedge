import { beforeEach, describe, expect, test, vi } from "vitest"
import { render, screen, waitFor } from "@/test/test-utils"
import SourceView from "./SourceView"

const { getSource, getRepositoryInfo, getReadme } = vi.hoisted(() => ({
  getSource: vi.fn(),
  getRepositoryInfo: vi.fn(),
  getReadme: vi.fn(),
}))
vi.mock("@/client/sdk.gen", () => ({ RepositoriesService: { getSource, getRepositoryInfo, getReadme } }))
vi.mock("@/components/Repository/RepoStats", () => ({
  default: ({ showStatistics }: { showStatistics: boolean }) => (
    <div>{showStatistics ? "Repository statistics" : "Repository navigation"}</div>
  ),
}))
vi.mock("@/components/Repository/FileBrowser", () => ({ default: () => <div data-testid="file-tree">Files</div> }))
vi.mock("@/components/Repository/ReadmeViewer", () => ({ default: () => <div>README content</div> }))
vi.mock("@/components/Repositories/RepoBreadcrumbs", () => ({ default: () => <div>Path</div> }))
vi.mock("@/components/Repositories/CodeViewer", () => ({ default: () => <div>File content</div> }))
const props = { owner: "owner", repo: "repo", mode: "branch" as const, refName: "main", path: "" }

describe("Source loading", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getRepositoryInfo.mockResolvedValue({ data: { branch_count: 1 } })
  })
  test("does not request or reserve a README for a directory without one", async () => {
    getSource.mockResolvedValue({ data: { entries: [{ name: "src", path: "src", type: "tree" }] } })
    render(<SourceView {...props} />)
    expect(await screen.findByTestId("file-tree")).toBeInTheDocument()
    expect(screen.getByText("Repository statistics")).toBeInTheDocument()
    expect(screen.queryByRole("status", { name: "Loading README" })).not.toBeInTheDocument()
    expect(getReadme).not.toHaveBeenCalled()
  })
  test("shows statistics only at the root of branch and commit trees", async () => {
    getSource.mockResolvedValue({ data: { entries: [] } })
    const { rerender } = render(<SourceView {...props} path="src" />)
    expect(await screen.findByText("Repository navigation")).toBeInTheDocument()
    expect(screen.queryByText("Repository statistics")).not.toBeInTheDocument()
    rerender(<SourceView {...props} mode="commit" refName={"a".repeat(40)} path="src" />)
    expect(await screen.findByText("Repository navigation")).toBeInTheDocument()
    expect(screen.queryByText("Repository statistics")).not.toBeInTheDocument()
    rerender(<SourceView {...props} mode="commit" refName={"a".repeat(40)} />)
    expect(await screen.findByText("Repository statistics")).toBeInTheDocument()
  })
  test("shows README loading only after the listing confirms a README file", async () => {
    getSource.mockResolvedValue({ data: { entries: [{ name: "README.md", path: "README.md", type: "blob" }] } })
    let finish: (value: { data: { html: string; content: string; filename: string } }) => void = () => {}
    getReadme.mockReturnValue(
      new Promise((resolve) => {
        finish = resolve
      }),
    )
    render(<SourceView {...props} />)
    expect(await screen.findByRole("status", { name: "Loading README" })).toBeInTheDocument()
    finish({ data: { html: "<p>Hello</p>", content: "Hello", filename: "README.md" } })
    expect(await screen.findByText("README content")).toBeInTheDocument()
  })
  test("uses the file skeleton for an extensionless direct link and replaces it with content", async () => {
    let finish: (value: { data: { content: string } }) => void = () => {}
    const file = new Promise((resolve) => {
      finish = resolve
    })
    getSource.mockImplementation(({ query }) =>
      query.source_path === "LICENSE"
        ? file
        : Promise.resolve({
            data: {
              entries: [{ name: "LICENSE", path: "LICENSE", type: "blob" }],
            },
          }),
    )
    render(<SourceView {...props} path="LICENSE" />)
    expect(await screen.findByRole("status", { name: "Loading file" })).toBeInTheDocument()
    expect(screen.queryByText("Repository statistics")).not.toBeInTheDocument()
    expect(screen.queryByRole("status", { name: "Loading directory" })).not.toBeInTheDocument()
    finish({ data: { content: "MIT License" } })
    await waitFor(() => expect(screen.getByText("File content")).toBeInTheDocument())
    expect(getReadme).not.toHaveBeenCalled()
  })
})
