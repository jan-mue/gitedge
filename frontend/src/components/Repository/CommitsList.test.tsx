import { HttpResponse } from "msw"
import { describe, expect, test, vi } from "vitest"
import { handleReleasesListTags, handleRepositoriesListBranches, handleRepositoriesListCommits } from "@/client/msw.gen"
import { server } from "@/test/server"
import { render, screen } from "@/test/test-utils"
import { CommitsList } from "./CommitsList"

const navigate = vi.hoisted(() => vi.fn())
vi.mock("@tanstack/react-router", () => ({ useNavigate: () => navigate }))

describe("Commit reference selection", () => {
  test("requests tag history explicitly and preserves the file filter when switching refs", async () => {
    const requests: URL[] = []
    server.use(
      handleRepositoriesListCommits(({ request }) => {
        const url = new URL(request.url)
        requests.push(url)
        return HttpResponse.json({ data: [], count: 0, ref: url.searchParams.get("ref") })
      }),
      handleRepositoriesListBranches({ body: [{ name: "main", is_default: true }] }),
      handleReleasesListTags({ body: { data: [{ name: "main", commit_sha: "a".repeat(40) }], count: 1 } }),
    )
    const { user } = render(<CommitsList owner="owner" repo="repo" tag="main" filePath="src/app.tsx" />)
    await user.click(await screen.findByRole("button", { name: "Switch branch" }))
    expect(requests[0].searchParams.get("ref")).toBe("refs/tags/main")
    expect(requests[0].searchParams.get("file_path")).toBe("src/app.tsx")
    expect(screen.getByRole("tab", { name: "Tags" })).toHaveAttribute("aria-selected", "true")
    await user.click(screen.getByRole("tab", { name: "Branches" }))
    await user.click(await screen.findByRole("option", { name: "main" }))
    expect(navigate).toHaveBeenCalledWith({
      to: "/$owner/$repo/commits/branch/$branch",
      params: { owner: "owner", repo: "repo", branch: "main" },
      search: { path: "src/app.tsx" },
    })
    await user.click(screen.getByRole("button", { name: "Switch branch" }))
    await user.click(await screen.findByRole("option", { name: "main" }))
    expect(navigate).toHaveBeenLastCalledWith({
      to: "/$owner/$repo/commits/tag/$tag",
      params: { owner: "owner", repo: "repo", tag: "main" },
      search: { path: "src/app.tsx" },
    })
  })
})
