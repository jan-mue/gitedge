import { HttpResponse } from "msw"
import { useState } from "react"
import { describe, expect, test, vi } from "vitest"
import { handleRepositoriesGetDiffFile } from "@/client/msw.gen"
import { server } from "@/test/server"
import { render, screen, within } from "@/test/test-utils"
import { DiffViewer } from "./DiffViewer"
import { comparisonFixture } from "./diff-fixtures"

const Review = () => {
  const [paths, setPaths] = useState<string[]>([])
  return (
    <DiffViewer
      {...comparisonFixture}
      reviewedPaths={paths}
      onReviewed={(path, viewed) => setPaths(viewed ? [path] : [])}
    />
  )
}

describe("DiffViewer", () => {
  test("file links use the displayed head, or the base revision for deleted files", () => {
    const head = "b".repeat(40)
    const base = "a".repeat(40)
    render(
      <DiffViewer
        {...comparisonFixture}
        files={[
          comparisonFixture.files[0],
          { ...comparisonFixture.files[1], path: "old file #1.py", change_type: "delete" },
        ]}
        diffSource={{ owner: "owner", repo: "repo", base, head }}
      />,
    )
    expect(screen.getByRole("link", { name: "View file src/config.py" })).toHaveAttribute(
      "href",
      `/owner/repo/src/commit/${head}/src/config.py`,
    )
    expect(screen.getByRole("link", { name: "View original file old file #1.py" })).toHaveAttribute(
      "href",
      `/owner/repo/src/commit/${base}/old%20file%20%231.py`,
    )
  })
  test("viewed files collapse, allow manual expansion, and expand when unmarked", async () => {
    const { user } = render(<Review />)
    await user.click(screen.getByRole("checkbox", { name: "Mark src/config.py as viewed" }))
    expect(screen.getByRole("button", { name: "Expand src/config.py" })).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Expand src/config.py" }))
    expect(screen.getByRole("button", { name: "Collapse src/config.py" })).toBeInTheDocument()
    await user.click(screen.getByRole("checkbox", { name: "Mark src/config.py as viewed" }))
    expect(screen.getByRole("button", { name: "Collapse src/config.py" })).toBeInTheDocument()
    await user.click(screen.getByRole("checkbox", { name: "Mark src/config.py as viewed" }))
    expect(screen.getByRole("button", { name: "Expand src/config.py" })).toBeInTheDocument()
  })
  test("renders backend syntax and inline tokens in both layouts", async () => {
    const { user, container } = render(<DiffViewer {...comparisonFixture} />)
    expect(container.querySelector('[data-syntax="literal-number"][data-changed]')).toHaveTextContent("12")
    expect(screen.getAllByText("42")).toHaveLength(2)
    await user.click(screen.getByRole("button", { name: "Split" }))
    expect(container.querySelectorAll(".diff-split-row")).toHaveLength(4)
    expect(screen.getAllByText("42")).toHaveLength(2)
    await user.click(screen.getByRole("button", { name: "Wrap lines" }))
    expect(screen.getByTestId("diff-viewer")).toHaveAttribute("data-wrap", "true")
  })

  test("filters and navigates files and expands a collapsed target", async () => {
    const { user } = render(<DiffViewer {...comparisonFixture} />)
    await user.click(screen.getByRole("button", { name: "Collapse src/config.py" }))
    expect(
      within(screen.getByRole("region", { name: "Diff for src/config.py" })).queryByText("42"),
    ).not.toBeInTheDocument()
    await user.click(
      within(screen.getByRole("navigation", { name: "Changed files" })).getByRole("button", { name: /src\/config.py/ }),
    )
    expect(within(screen.getByRole("region", { name: "Diff for src/config.py" })).getByText("42")).toBeInTheDocument()
    expect(HTMLElement.prototype.scrollIntoView).toHaveBeenCalled()
    await user.type(screen.getByRole("textbox", { name: "Filter changed files" }), "tests/")
    expect(screen.queryByRole("region", { name: "Diff for src/config.py" })).not.toBeInTheDocument()
    expect(screen.getByRole("region", { name: "Diff for tests/test_config.py" })).toBeInTheDocument()
  })

  test("anchors comments to deleted or added line and keeps editor text on failure", async () => {
    const save = vi.fn().mockRejectedValueOnce(new Error("Offline")).mockResolvedValueOnce(undefined)
    const { user } = render(<DiffViewer {...comparisonFixture} onAddComment={save} />)
    await user.click(screen.getByRole("button", { name: "Comment on src/config.py old line 1" }))
    await user.type(screen.getByRole("textbox", { name: "Line comment" }), "Keep this configurable")
    await user.click(screen.getByRole("button", { name: "Add to review" }))
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to save")
    expect(screen.getByRole("textbox", { name: "Line comment" })).toHaveValue("Keep this configurable")
    await user.click(screen.getByRole("button", { name: "Add to review" }))
    expect(save).toHaveBeenLastCalledWith({
      path: "src/config.py",
      side: "old",
      line: 1,
      body: "Keep this configurable",
    })
  })
})

describe("Lazy diff files", () => {
  test("reuses immutable query results after collapsing and expanding", async () => {
    const requests: string[] = []
    const file = comparisonFixture.files[0]
    server.use(
      handleRepositoriesGetDiffFile(({ request }) => {
        requests.push(request.url)
        return HttpResponse.json(file)
      }),
    )
    const { user } = render(
      <DiffViewer
        files={[{ ...file, diff_loaded: false, diff_line_count: 3, hunks: [] }]}
        additions={1}
        deletions={1}
        diffSource={{ owner: "owner", repo: "repo", base: "a".repeat(40), head: "b".repeat(40) }}
      />,
    )
    expect(await screen.findByText("42")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Collapse src/config.py" }))
    await user.click(screen.getByRole("button", { name: "Expand src/config.py" }))
    expect(await screen.findByText("42")).toBeInTheDocument()
    expect(requests).toHaveLength(1)
    expect(new URL(requests[0]).searchParams.get("head")).toBe("b".repeat(40))
  })

  test("shows a retry action when a per-file request fails", async () => {
    let unavailable = true
    const file = comparisonFixture.files[0]
    server.use(
      handleRepositoriesGetDiffFile(() =>
        unavailable ? HttpResponse.json({ detail: "Unavailable" }, { status: 503 }) : HttpResponse.json(file),
      ),
    )
    const { user } = render(
      <DiffViewer
        files={[{ ...file, diff_loaded: false, diff_line_count: 3, hunks: [] }]}
        additions={1}
        deletions={1}
        diffSource={{ owner: "owner", repo: "repo", base: "a".repeat(40), head: "b".repeat(40) }}
      />,
    )
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load this diff")
    unavailable = false
    await user.click(screen.getByRole("button", { name: "Retry" }))
    expect(await screen.findByText("42")).toBeInTheDocument()
  })
})
