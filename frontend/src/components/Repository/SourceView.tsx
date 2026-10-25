import { useQuery } from "@tanstack/react-query"
import type { FileContent, TreeListing } from "@/client"
import {
  repositoriesGetReadmeOptions,
  repositoriesGetRepositoryInfoOptions,
  repositoriesGetSourceOptions,
} from "@/client/@tanstack/react-query.gen"
import { Skeleton } from "@/components/design-system"
import CodeViewer from "@/components/Repositories/CodeViewer"
import RepoBreadcrumbs from "@/components/Repositories/RepoBreadcrumbs"
import type { SourceMode } from "@/components/Repositories/SourceLink"
import FileBrowser from "@/components/Repository/FileBrowser"
import ReadmeViewer from "@/components/Repository/ReadmeViewer"
import { RepoStats } from "@/components/Repository/RepoStats"
import { RepositoryError } from "@/components/Repository/RepositoryLoading"
import SourceLoading from "@/components/Repository/SourceLoading"

interface SourceViewProps {
  owner: string
  repo: string
  mode: SourceMode
  refName: string
  path: string
}

const readmeNames = new Set(["README.md", "README.MD", "readme.md", "README", "README.txt", "README.rst", "Readme.md"])
const sourceTree = (source?: FileContent | TreeListing) => (source && "entries" in source ? source : undefined)
const sourceBlob = (source?: FileContent | TreeListing) => (source && "content" in source ? source : undefined)
const sourceKind = (path: string, parent?: FileContent | TreeListing) => {
  if (!path) return "tree"
  const tree = sourceTree(parent)
  return tree?.entries.find((entry) => entry.path === path)?.type
}
const containsReadme = (tree?: TreeListing) =>
  tree?.entries.some((entry) => entry.type === "blob" && readmeNames.has(entry.name)) ?? false
const useSourceData = ({ owner, repo, mode, refName, path }: SourceViewProps) => {
  const revision = mode === "tag" ? `refs/tags/${refName}` : refName
  const {
    data: source,
    isPending,
    isError,
    refetch,
  } = useQuery({
    ...repositoriesGetSourceOptions({ path: { owner, repo }, query: { ref: revision, source_path: path } }),
    retry: false,
  })
  const tree = sourceTree(source)
  const blob = sourceBlob(source)
  const parentPath = path.split("/").slice(0, -1).join("/")
  const { data: parent } = useQuery({
    ...repositoriesGetSourceOptions({ path: { owner, repo }, query: { ref: revision, source_path: parentPath } }),
    enabled: Boolean(path) && isPending,
    retry: false,
  })
  const kind = sourceKind(path, parent)
  const hasReadme = containsReadme(tree)
  const {
    data: repoInfo,
    isPending: infoPending,
    isError: infoError,
    refetch: refetchInfo,
  } = useQuery(repositoriesGetRepositoryInfoOptions({ path: { owner, repo }, query: { ref: revision } }))
  const {
    data: readme,
    isPending: readmePending,
    isFetching: readmeFetching,
  } = useQuery({
    ...repositoriesGetReadmeOptions({ path: { owner, repo }, query: { ref: revision, tree_path: path } }),
    retry: false,
    enabled: hasReadme,
  })

  const empty = !path && repoInfo?.branch_count === 0

  return {
    revision,
    blob,
    isPending,
    isError,
    refetch,
    tree,
    kind,
    hasReadme,
    repoInfo,
    infoPending,
    infoError,
    refetchInfo,
    readme,
    readmePending,
    readmeFetching,
    empty,
  }
}

export const SourceView = ({ owner, repo, mode, refName, path }: SourceViewProps) => {
  const {
    revision,
    blob,
    isPending,
    isError,
    refetch,
    tree,
    kind,
    hasReadme,
    repoInfo,
    infoPending,
    infoError,
    refetchInfo,
    readme,
    readmePending,
    readmeFetching,
    empty,
  } = useSourceData({ owner, repo, mode, refName, path })
  if (blob) {
    const parts = path.split("/").filter(Boolean)
    return (
      <div className="flex flex-col gap-4">
        <RepoBreadcrumbs owner={owner} repo={repo} path={path} mode={mode} refName={refName} />
        <CodeViewer
          file={blob}
          commitSha={repoInfo?.last_commit?.sha}
          lastCommit={repoInfo?.last_commit}
          lastCommitLoading={infoPending}
          lastCommitError={infoError}
          onRetryLastCommit={() => refetchInfo()}
          backLink={{ owner, repo, mode, refName, path: parts.slice(0, -1).join("/") }}
        />
      </div>
    )
  }
  if ((isPending || (isError && infoPending)) && kind !== "tree")
    return (
      <div className="flex flex-col gap-4">
        <RepoBreadcrumbs owner={owner} repo={repo} path={path} mode={mode} refName={refName} />
        <SourceLoading kind={kind} />
      </div>
    )
  const renderReadme = () =>
    hasReadme && readme ? (
      <ReadmeViewer html={readme.html} content={readme.content} filename={readme.filename} />
    ) : (
      hasReadme &&
      readmePending &&
      readmeFetching && (
        <div role="status" aria-label="Loading README" className="space-y-3 rounded-lg border p-6">
          <Skeleton appearance="heading" />
          <Skeleton appearance="line" />
          <Skeleton appearance="paragraph" />
        </div>
      )
    )
  const renderDirectory = () =>
    isPending || (isError && infoPending) ? (
      <SourceLoading kind="tree" />
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
          lastCommitLoading={infoPending}
          lastCommitError={infoError}
          onRetryLastCommit={() => refetchInfo()}
        />
        {renderReadme()}
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
    ) : null

  return (
    <div className="flex flex-col gap-4">
      <RepoStats
        owner={owner}
        repo={repo}
        gitRef={mode === "commit" ? refName.slice(0, 10) : refName}
        revision={revision}
        mode={mode}
        showStatistics={!path}
      />
      {renderDirectory()}
    </div>
  )
}
