import { HttpResponse } from "msw"
import { beforeEach, describe, expect, test, vi } from "vitest"
import type { FileContent, ReadmeContent } from "@/client"
import {
  handleRepositoriesGetReadme,
  handleRepositoriesGetRepositoryInfo,
  handleRepositoriesGetSource,
} from "@/client/msw.gen"
import { server } from "@/test/server"
import { render, screen, waitFor } from "@/test/test-utils"
import SourceView from "./SourceView"

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
    server.use(
      handleRepositoriesGetRepositoryInfo({
        body: { owner: "owner", name: "repo", default_branch: "main", branch_count: 1, tag_count: 0 },
      }),
    )
  })
  test("does not request or reserve a README for a directory without one", async () => {
    const getReadme = vi.fn(() => HttpResponse.json({ html: "", content: "", filename: "README.md" }))
    server.use(
      handleRepositoriesGetSource({
        body: { entries: [{ name: "src", path: "src", type: "tree", size: null }], tree_path: "", ref: "main" },
      }),
      handleRepositoriesGetReadme(getReadme),
    )
    render(<SourceView {...props} />)
    expect(await screen.findByTestId("file-tree")).toBeInTheDocument()
    expect(screen.getByText("Repository statistics")).toBeInTheDocument()
    expect(screen.queryByRole("status", { name: "Loading README" })).not.toBeInTheDocument()
    expect(getReadme).not.toHaveBeenCalled()
  })
  test("shows statistics only at the root of branch and commit trees", async () => {
    server.use(handleRepositoriesGetSource({ body: { entries: [], tree_path: "", ref: "main" } }))
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
    let finish: (value: ReadmeContent) => void = () => {}
    const response = new Promise<ReadmeContent>((resolve) => {
      finish = resolve
    })
    server.use(
      handleRepositoriesGetSource({
        body: {
          entries: [{ name: "README.md", path: "README.md", type: "blob", size: 5 }],
          tree_path: "",
          ref: "main",
        },
      }),
      handleRepositoriesGetReadme(async () => HttpResponse.json(await response)),
    )
    render(<SourceView {...props} />)
    expect(await screen.findByRole("status", { name: "Loading README" })).toBeInTheDocument()
    finish({ html: "<p>Hello</p>", content: "Hello", filename: "README.md" })
    expect(await screen.findByText("README content")).toBeInTheDocument()
  })
  test("uses the file skeleton for an extensionless direct link and replaces it with content", async () => {
    let finish: (value: FileContent) => void = () => {}
    const file = new Promise<FileContent>((resolve) => {
      finish = resolve
    })
    const getReadme = vi.fn(() => HttpResponse.json({ html: "", content: "", filename: "README.md" }))
    server.use(
      handleRepositoriesGetSource(async ({ request }) =>
        HttpResponse.json(
          new URL(request.url).searchParams.get("source_path") === "LICENSE"
            ? await file
            : { entries: [{ name: "LICENSE", path: "LICENSE", type: "blob", size: 11 }], tree_path: "", ref: "main" },
        ),
      ),
      handleRepositoriesGetReadme(getReadme),
    )
    render(<SourceView {...props} path="LICENSE" />)
    expect(await screen.findByRole("status", { name: "Loading file" })).toBeInTheDocument()
    expect(screen.queryByText("Repository statistics")).not.toBeInTheDocument()
    expect(screen.queryByRole("status", { name: "Loading directory" })).not.toBeInTheDocument()
    finish({
      name: "LICENSE",
      path: "LICENSE",
      content: "MIT License",
      size: 11,
      highlighted_html: "",
      css: "",
      css_dark: "",
      language: "text",
      line_count: 1,
    })
    await waitFor(() => expect(screen.getByText("File content")).toBeInTheDocument())
    expect(getReadme).not.toHaveBeenCalled()
  })
})
