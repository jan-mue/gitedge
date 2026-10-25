import { HttpResponse } from "msw"
import type { ReactNode } from "react"
import { beforeEach, describe, expect, test, vi } from "vitest"
import type { FileContent, ReadmeContent, RepositoryInfo } from "@/client"
import {
  handleRepositoriesGetReadme,
  handleRepositoriesGetRepositoryInfo,
  handleRepositoriesGetSource,
} from "@/client/msw.gen"
import { server } from "@/test/server"
import { render, screen, waitFor } from "@/test/test-utils"
import { SourceView } from "./SourceView"

vi.mock("@/components/Repository/RepoStats", () => ({
  RepoStats: ({ showStatistics }: { showStatistics: boolean }) => (
    <div>{showStatistics ? "Repository statistics" : "Repository navigation"}</div>
  ),
}))
vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => vi.fn(),
  Link: ({ children, "data-testid": testId }: { children: ReactNode; "data-testid"?: string }) => (
    <a href="/" data-testid={testId}>
      {children}
    </a>
  ),
}))
vi.mock("@/components/Repository/ReadmeViewer", () => ({ default: () => <div>README content</div> }))
vi.mock("@/components/Repositories/RepoBreadcrumbs", () => ({ default: () => <div>Path</div> }))
vi.mock("@/components/Repositories/CodeViewer", () => ({ default: () => <div>File content</div> }))
const props = { owner: "owner", repo: "repo", mode: "branch" as const, refName: "main", path: "" }

describe("Source loading", () => {
  const commit = { sha: "abcdef1234567890", message: "Latest commit", author: "Jan", timestamp: 1791663993 }
  const metadata = {
    owner: "owner",
    name: "repo",
    default_branch: "main",
    branch_count: 1,
    tag_count: 0,
    last_commit: commit,
  }

  test("keeps the commit header while metadata loads and fills it when the response arrives", async () => {
    let finish: (value: RepositoryInfo) => void = () => {}
    const info = new Promise<RepositoryInfo>((resolve) => {
      finish = resolve
    })
    server.use(
      handleRepositoriesGetSource({ body: { entries: [], tree_path: "", ref: "main" } }),
      handleRepositoriesGetRepositoryInfo(async () => HttpResponse.json(await info)),
    )
    render(<SourceView {...props} />)
    expect(await screen.findByRole("status", { name: "Loading latest commit" })).toBeInTheDocument()
    expect(screen.getByTestId("file-tree")).toBeInTheDocument()
    finish(metadata)
    expect(await screen.findByTestId("last-commit-sha")).toHaveTextContent("abcdef1234")
    expect(screen.getByTestId("last-commit-header")).toHaveTextContent("Latest commit")
  })

  test("keeps the file list and offers retry when commit metadata fails", async () => {
    server.use(
      handleRepositoriesGetSource({ body: { entries: [], tree_path: "", ref: "main" } }),
      handleRepositoriesGetRepositoryInfo(() => new HttpResponse(null, { status: 503 }), { once: true }),
    )
    const { user } = render(<SourceView {...props} />)
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load the latest commit")
    expect(screen.getByTestId("file-tree")).toBeInTheDocument()
    server.use(handleRepositoriesGetRepositoryInfo({ body: metadata }))
    await user.click(screen.getByRole("button", { name: "Try again" }))
    expect(await screen.findByTestId("last-commit-sha")).toHaveTextContent("abcdef1234")
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })
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
  test("uses the tag namespace for source, metadata and README requests", async () => {
    const refs: string[] = []
    const record = (request: Request) => refs.push(new URL(request.url).searchParams.get("ref") ?? "")
    server.use(
      handleRepositoriesGetSource(({ request }) => {
        record(request)
        return HttpResponse.json({
          entries: [{ name: "README.md", path: "README.md", type: "blob", size: 5 }],
          tree_path: "",
          ref: "refs/tags/main",
        })
      }),
      handleRepositoriesGetRepositoryInfo(({ request }) => {
        record(request)
        return HttpResponse.json({
          owner: "owner",
          name: "repo",
          default_branch: "main",
          branch_count: 1,
          tag_count: 1,
        })
      }),
      handleRepositoriesGetReadme(({ request }) => {
        record(request)
        return HttpResponse.json({ filename: "README.md", content: "Hello", html: "<p>Hello</p>" })
      }),
    )
    render(<SourceView {...props} mode="tag" refName="main" />)
    expect(await screen.findByText("README content")).toBeInTheDocument()
    expect(refs).toHaveLength(3)
    expect(refs.every((ref) => ref === "refs/tags/main")).toBe(true)
  })
})
