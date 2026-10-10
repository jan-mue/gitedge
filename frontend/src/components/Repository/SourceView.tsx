import { useQuery } from "@tanstack/react-query"
import {
  repositoriesGetReadmeOptions,
  repositoriesGetRepositoryInfoOptions,
  repositoriesGetSourceOptions,
} from "@/client/@tanstack/react-query.gen"
import CodeViewer from "@/components/Repositories/CodeViewer"
import RepoBreadcrumbs from "@/components/Repositories/RepoBreadcrumbs"
import type { SourceMode } from "@/components/Repositories/SourceLink"
import FileBrowser from "@/components/Repository/FileBrowser"
import ReadmeViewer from "@/components/Repository/ReadmeViewer"
import RepoStats from "@/components/Repository/RepoStats"
import RepositoryLoading, { RepositoryError } from "@/components/Repository/RepositoryLoading"
import { Skeleton } from "@/components/ui/skeleton"

interface SourceViewProps {
  owner: string
  repo: string
  mode: SourceMode
  refName: string
  path: string
}

const SourceView = ({ owner, repo, mode, refName, path }: SourceViewProps) => {
  const {
    data: source,
    isPending,
    isError,
    refetch,
  } = useQuery({
    ...repositoriesGetSourceOptions({ path: { owner, repo }, query: { ref: refName, source_path: path } }),
    retry: false,
  })
  const tree = source && "entries" in source ? source : undefined
  const blob = source && "content" in source ? source : undefined
  const { data: repoInfo, isPending: infoPending } = useQuery(
    repositoriesGetRepositoryInfoOptions({ path: { owner, repo }, query: { ref: refName } }),
  )
  const {
    data: readme,
    isPending: readmePending,
    isFetching: readmeFetching,
  } = useQuery({
    ...repositoriesGetReadmeOptions({ path: { owner, repo }, query: { ref: refName, tree_path: path } }),
    retry: false,
    enabled: Boolean(tree),
  })

  if (blob) {
    const parts = path.split("/").filter(Boolean)
    return (
      <div className="flex flex-col gap-4">
        <RepoBreadcrumbs owner={owner} repo={repo} path={path} mode={mode} refName={refName} />
        <CodeViewer
          file={blob}
          commitSha={repoInfo?.last_commit?.sha}
          backLink={{ owner, repo, mode, refName, path: parts.slice(0, -1).join("/") }}
        />
      </div>
    )
  }
  const empty = !path && repoInfo?.branch_count === 0
  return (
    <div className="flex flex-col gap-4">
      <RepoStats
        owner={owner}
        repo={repo}
        gitRef={mode === "commit" ? refName.slice(0, 10) : refName}
        revision={refName}
      />
      {isPending || (isError && infoPending) ? (
        <RepositoryLoading label="Loading source" />
      ) : tree ? (
        <>
          {path && <RepoBreadcrumbs owner={owner} repo={repo} path={path} mode={mode} refName={refName} />}
          <FileBrowser
            entries={tree.entries}
            owner={owner}
            repo={repo}
            mode={mode}
            refName={refName}
            treePath={path}
            lastCommit={repoInfo?.last_commit}
          />
          {readme ? (
            <ReadmeViewer html={readme.html} content={readme.content} filename={readme.filename} />
          ) : (
            readmePending &&
            readmeFetching && (
              <div role="status" aria-label="Loading README" className="space-y-3 rounded-lg border p-6">
                <Skeleton className="h-6 w-1/3" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-2/3" />
              </div>
            )
          )}
        </>
      ) : empty ? (
        <div
          className="flex flex-col items-center justify-center rounded-lg border bg-card px-4 py-16 text-center"
          data-testid="empty-repository"
        >
          <h2 className="text-lg font-semibold">This repository is empty</h2>
          <p className="mt-1 text-sm text-muted-foreground">Push some code to get started:</p>
          <code className="mt-3 max-w-full overflow-x-auto rounded bg-secondary px-3 py-2 font-mono text-xs">
            git clone {window.location.origin}/{owner}/{repo}.git
          </code>
        </div>
      ) : isError ? (
        <RepositoryError message="Unable to load this path or revision." retry={() => refetch()} />
      ) : null}
    </div>
  )
}
export default SourceView
