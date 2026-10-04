import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"

import { RepositoriesService } from "@/client"
import RepoBreadcrumbs from "@/components/Repositories/RepoBreadcrumbs"
import RepositoryLayout from "@/components/Repositories/RepositoryLayout"
import FileBrowser from "@/components/Repository/FileBrowser"
import ReadmeViewer from "@/components/Repository/ReadmeViewer"
import RepoStats from "@/components/Repository/RepoStats"

interface SearchParams {
  ref?: string
  path?: string
}

export const Route = createFileRoute("/_layout/$owner/$repo/")({
  component: RepositoryTree,
  validateSearch: (search: Record<string, unknown>): SearchParams => ({
    ref: (search.ref as string) || undefined,
    path: (search.path as string) || undefined,
  }),
  head: ({ params }) => ({
    meta: [
      {
        title: `${params.owner}/${params.repo} - GitEdge`,
      },
    ],
  }),
})

function TreeContent() {
  const { owner, repo } = Route.useParams()
  const { ref: searchRef, path: treePath } = Route.useSearch()
  const repoPath = owner === "_" ? `${repo}.git` : `${owner}/${repo}.git`

  const {
    data: tree,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["tree", repoPath, searchRef ?? "main", treePath ?? ""],
    queryFn: async () =>
      (
        await RepositoriesService.getTree({
          path: { path: repoPath },
          query: { ref: searchRef, tree_path: treePath },
        })
      ).data,
    retry: false,
  })

  const { data: repoInfo } = useQuery({
    queryKey: ["repoInfo", repoPath, searchRef],
    queryFn: async () =>
      (
        await RepositoriesService.getRepositoryInfo({
          path: { path: repoPath },
          query: { ref: searchRef },
        })
      ).data,
  })

  const { data: readme } = useQuery({
    queryKey: ["readme", repoPath, searchRef, treePath ?? ""],
    queryFn: async () =>
      (
        await RepositoriesService.getReadme({
          path: { path: repoPath },
          query: { ref: searchRef, tree_path: treePath },
        })
      ).data,
    retry: false,
    enabled: Boolean(tree),
  })

  const gitRef = tree?.ref ?? searchRef ?? "main"

  return (
    <div className="flex flex-col gap-4">
      <RepoStats owner={owner} repo={repo} gitRef={gitRef} searchRef={searchRef} />

      {tree ? (
        <>
          {treePath && <RepoBreadcrumbs owner={owner} repo={repo} path={treePath} searchRef={searchRef} />}

          <FileBrowser
            entries={tree.entries}
            owner={owner}
            repo={repo}
            treePath={treePath}
            searchRef={searchRef}
            lastCommit={repoInfo?.last_commit}
          />

          {readme && <ReadmeViewer html={readme.html} content={readme.content} filename={readme.filename} />}
        </>
      ) : (
        !isLoading && (
          <div
            className="flex flex-col items-center justify-center rounded-lg border border-border bg-card py-16 text-center"
            data-testid="empty-repository"
          >
            <h2 className="text-lg font-semibold text-foreground">
              {isError ? "This repository is empty" : "No files"}
            </h2>
            <p className="mt-1 max-w-md text-sm text-muted-foreground">Push some code to get started:</p>
            <code className="mt-3 rounded bg-secondary px-3 py-2 font-mono text-xs text-foreground">
              git clone {window.location.origin}/{repoPath.replace(/\.git$/, "")}.git
            </code>
          </div>
        )
      )}
    </div>
  )
}

function RepositoryTree() {
  const { owner, repo } = Route.useParams()

  return (
    <RepositoryLayout owner={owner} repo={repo}>
      <TreeContent />
    </RepositoryLayout>
  )
}
