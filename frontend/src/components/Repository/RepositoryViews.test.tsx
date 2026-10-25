import { HttpResponse } from "msw"
import type { ReactNode } from "react"
import { beforeEach, describe, expect, test, vi } from "vitest"
import type { CommitDetail as Commit, ReleasePublic, Repository } from "@/client"
import {
  handleOrganizationsListOrganizations,
  handleProfilesListUserRepositories,
  handleProfilesListUserStarredRepositories,
  handleProfilesReadUserByUsername,
  handleReleasesListReleases,
  handleReleasesListTags,
  handleRepositoriesCompareRevisions,
  handleRepositoriesCreateRepository,
  handleRepositoriesGetBlame,
  handleRepositoriesGetCommit,
  handleRepositoriesGetRepository,
  handleRepositoriesListBranches,
  handleRepositoriesUpdateRepository,
  handleStarsGetStarState,
} from "@/client/msw.gen"
import { GlobalNav } from "@/components/GlobalNav"
import { UserProfile } from "@/components/Profile/UserProfile"
import { BlameView } from "@/components/Repository/BlameView"
import { BranchesList } from "@/components/Repository/BranchesList"
import { CommitDetail } from "@/components/Repository/CommitDetail"
import { CompareView } from "@/components/Repository/CompareView"
import { ReleasesList } from "@/components/Repository/ReleasesList"
import { RepositorySettings } from "@/components/Repository/RepositorySettings"
import { server } from "@/test/server"
import { render, screen, waitFor } from "@/test/test-utils"

const navigate = vi.hoisted(() => vi.fn())
vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => navigate,
  useParams: () => ({ owner: "owner", repo: "repo", hash: "abc123" }),
  useSearch: () => ({ base: "main", head: "feature" }),
  Link: ({ children, "data-testid": testId }: { children: ReactNode; "data-testid"?: string }) => (
    <a href="/" data-testid={testId}>
      {children}
    </a>
  ),
}))
vi.mock("@/hooks/useAuth", () => ({
  default: () => ({
    user: { id: "user-1", name: "owner", email: "owner@example.com", is_superuser: false },
    logout: vi.fn(),
  }),
}))

const repository: Repository = {
  owner: "owner",
  name: "repo",
  default_branch: "main",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
}
const commit: Commit = {
  sha: "abc123",
  message: "Fix navigation\n\nKeep keyboard focus",
  author: "Alice",
  author_email: "alice@example.com",
  timestamp: 1700000000,
  parents: ["parent123"],
  files: [],
  additions: 0,
  deletions: 0,
}
const release: ReleasePublic = {
  id: "release-1",
  repo_owner: "owner",
  repo_name: "repo",
  tag_name: "v1.0.0",
  name: "First release",
  body: "Release notes",
  author_username: "owner",
  created_at: repository.created_at,
  updated_at: repository.updated_at,
}

beforeEach(() => {
  server.use(
    handleRepositoriesListBranches({ body: [{ name: "main", is_default: true }] }),
    handleReleasesListTags({ body: { data: [{ name: "v1.0.0", commit_sha: "abc123" }], count: 1 } }),
    handleRepositoriesGetRepository({ body: repository }),
    handleStarsGetStarState({ body: { is_starred: false, stars_count: 0 } }),
  )
})

describe("repository query views", () => {
  test("renders default branches and tag revisions", async () => {
    render(<BranchesList owner="owner" repo="repo" />)
    expect(await screen.findByTestId("branches-list")).toHaveTextContent("1 branch")
    expect(screen.getByText("default")).toBeInTheDocument()
    expect(screen.getByText("v1.0.0")).toBeInTheDocument()
    expect(screen.getByText("abc123")).toBeInTheDocument()
  })

  test("retries a failed branch request", async () => {
    server.use(handleRepositoriesListBranches(() => HttpResponse.json({ detail: "Unavailable" }, { status: 503 })))
    const { user } = render(<BranchesList owner="owner" repo="repo" />)
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load branches or tags")
    server.use(handleRepositoriesListBranches({ body: [{ name: "recovered", is_default: true }] }))
    await user.click(screen.getByRole("button", { name: "Try again" }))
    expect(await screen.findByText("recovered")).toBeInTheDocument()
  })

  test("groups consecutive blame lines and toggles escaped tabs", async () => {
    server.use(
      handleRepositoriesGetBlame({
        body: {
          path: "file.ts",
          revision: commit.sha,
          lines: [
            { number: 1, content: "\tfirst", commit },
            { number: 2, content: "second", commit },
          ],
        },
      }),
    )
    const { user } = render(<BlameView owner="owner" repo="repo" revision="main" path="file.ts" />)
    await screen.findByText("2 lines · Blame at main")
    expect(screen.getByRole("cell", { name: /Fix navigation/ })).toHaveAttribute("rowspan", "2")
    await user.click(screen.getByRole("button", { name: "Escape tabs" }))
    expect(screen.getByText("\\tfirst")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Unescape tabs" }))
    expect(screen.getByRole("button", { name: "Escape tabs" })).toBeInTheDocument()
  })

  test("renders commit metadata, parents, and the empty diff", async () => {
    server.use(handleRepositoriesGetCommit({ body: commit }))
    render(<CommitDetail />)
    expect(await screen.findByRole("heading", { name: "Fix navigation" })).toBeInTheDocument()
    expect(screen.getByText("Keep keyboard focus")).toBeInTheDocument()
    expect(screen.getByText("parent123")).toBeInTheDocument()
    expect(screen.getByText("No changed files in this comparison.")).toBeInTheDocument()
  })

  test("handles missing comparison revisions and submits trimmed refs", async () => {
    server.use(
      handleRepositoriesCompareRevisions({
        body: { base_commit: null, head_commit: null, files: [], additions: 0, deletions: 0 },
      }),
    )
    const { user } = render(<CompareView />)
    expect(await screen.findByText("One or both revisions could not be found.")).toBeInTheDocument()
    await user.clear(screen.getByLabelText("Head branch, tag, or commit"))
    await user.type(screen.getByLabelText("Head branch, tag, or commit"), " next ")
    await user.click(screen.getByRole("button", { name: "Compare" }))
    expect(navigate).toHaveBeenCalledWith({
      to: "/$owner/$repo/compare",
      params: { owner: "owner", repo: "repo" },
      search: { base: "main", head: "next" },
    })
  })

  test("renders releases and opens and cancels editing", async () => {
    server.use(handleReleasesListReleases({ body: { data: [release], count: 1 } }))
    const { user } = render(<ReleasesList owner="owner" repo="repo" />)
    expect(await screen.findByText("First release")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Edit" }))
    expect(screen.getByTestId("edit-release-name-input")).toHaveValue("First release")
    await user.click(screen.getByRole("button", { name: "Cancel" }))
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  test("preserves explicitly disabled merge settings when saving", async () => {
    server.use(handleRepositoriesGetRepository({ body: { ...repository, allow_merge_commit: false } }))
    const saved = vi.fn()
    server.use(
      handleRepositoriesUpdateRepository(async ({ request }) => {
        const body = await request.json()
        saved(body)
        return HttpResponse.json({ ...repository, ...body })
      }),
    )
    const { user } = render(<RepositorySettings owner="owner" repo="repo" />)
    const name = await screen.findByLabelText("Repository name *")
    expect(screen.getByRole("checkbox", { name: "Create merge commit" })).not.toBeChecked()
    await user.type(name, "-renamed")
    await user.click(screen.getByRole("button", { name: "Save settings" }))
    await waitFor(() =>
      expect(saved).toHaveBeenCalledWith(
        expect.objectContaining({ allow_merge_commit: false, allow_squash_merge: true, name: "repo-renamed" }),
      ),
    )
  })
})

test("switches a profile from owned to starred repositories", async () => {
  server.use(
    handleProfilesReadUserByUsername({
      body: { id: "user-1", name: "owner", principal_type: "user" },
    }),
    handleProfilesListUserRepositories({ body: { data: [repository], count: 1 } }),
    handleProfilesListUserStarredRepositories({
      body: { data: [{ ...repository, name: "starred-project" }], count: 1 },
    }),
  )
  const { user } = render(<UserProfile username="owner" />)
  expect(await screen.findByTestId("profile-repo-repo")).toBeInTheDocument()
  await user.click(await screen.findByTestId("profile-tab-starred"))
  expect(await screen.findByTestId("profile-repo-starred-project")).toBeInTheDocument()
  expect(screen.queryByTestId("profile-repo-repo")).not.toBeInTheDocument()
})

test("creates a repository from navigation and closes and resets its dialog", async () => {
  server.use(handleOrganizationsListOrganizations({ body: { data: [], count: 0 } }))
  const create = vi.fn()
  server.use(
    handleRepositoriesCreateRepository(async ({ request }) => {
      const body = await request.json()
      create(body)
      return HttpResponse.json({ ...repository, ...body }, { status: 201 })
    }),
  )
  const { user } = render(<GlobalNav />)
  await user.click(screen.getByRole("button", { name: "Create repository or organization" }))
  await user.click(screen.getByRole("menuitem", { name: "New Repository" }))
  await user.type(screen.getByTestId("new-repo-name"), " next ")
  await user.click(screen.getByRole("button", { name: "Create Repository" }))
  await waitFor(() => expect(create).toHaveBeenCalledWith({ owner: "owner", name: "next" }))
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
  expect(navigate).toHaveBeenCalledWith({ to: "/$owner/$repo", params: { owner: "owner", repo: "next" } })
})
