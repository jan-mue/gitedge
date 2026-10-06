import { useQuery } from "@tanstack/react-query"

import { RepositoriesService } from "@/client"
import CodeViewer from "@/components/Repositories/CodeViewer"
import RepoBreadcrumbs from "@/components/Repositories/RepoBreadcrumbs"
import type { SourceMode } from "@/components/Repositories/SourceLink"
import FileBrowser from "@/components/Repository/FileBrowser"
import ReadmeViewer from "@/components/Repository/ReadmeViewer"
import RepoStats from "@/components/Repository/RepoStats"

interface SourceViewProps {
  owner: string
  repo: string
  mode: SourceMode
  /** Branch name or commit SHA, depending on the mode. */
  refName: string
  /** Path within the repository, relative to the repo root. Empty for the root. */
  path: string
}

const SourceView = ({ owner, repo, mode, refName, path }: SourceViewProps) => {
  const repoPath = `${owner}/${repo}.git`

  const {
    data: tree,
    isLoading: treeLoading,
    isError: treeError,
  } = useQuery({
    queryKey: ["tree", repoPath, refName, path],
    queryFn: async () =>
      (await RepositoriesService.getTree({ path: { path: repoPath }, query: { ref: refName, tree_path: path } })).data,
    retry: false,
  })

  const isFile = Boolean(path) && treeError

  const { data: blob } = useQuery({
    queryKey: ["blob", repoPath, refName, path],
    queryFn: async () =>
      (await RepositoriesService.getBlob({ path: { path: repoPath }, query: { ref: refName, file_path: path } })).data,
    retry: false,
    enabled: isFile,
  })

  const { data: repoInfo } = useQuery({
    queryKey: ["repoInfo", repoPath, refName],
    queryFn: async () =>
      (await RepositoriesService.getRepositoryInfo({ path: { path: repoPath }, query: { ref: refName } })).data,
  })

  const { data: readme } = useQuery({
    queryKey: ["readme", repoPath, refName, path],
    queryFn: async () =>
      (await RepositoriesService.getReadme({ path: { path: repoPath }, query: { ref: refName, tree_path: path } }))
        .data,
    retry: false,
    enabled: Boolean(tree),
  })

  if (blob) {
    const parentParts = path.split("/").filter(Boolean)
    const parentPath = parentParts.length > 1 ? parentParts.slice(0, -1).join("/") : ""
    return (
      <div className="flex flex-col gap-4">
        <RepoBreadcrumbs owner={owner} repo={repo} path={path} mode={mode} refName={refName} />
        <CodeViewer file={blob} backLink={{ owner, repo, mode, refName, path: parentPath }} />
      </div>
    )
  }

  const gitRef = mode === "commit" ? refName.slice(0, 10) : (tree?.ref ?? refName)

  return (
    <div className="flex flex-col gap-4">
      <RepoStats owner={owner} repo={repo} gitRef={gitRef} revision={refName} />

      {tree ? (
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

          {readme && <ReadmeViewer html={readme.html} content={readme.content} filename={readme.filename} />}
        </>
      ) : (
        !treeLoading &&
        !isFile && (
          <div
            className="flex flex-col items-center justify-center rounded-lg border border-border bg-card py-16 text-center"
            data-testid="empty-repository"
          >
            <h2 className="text-lg font-semibold text-foreground">
              {treeError ? "This repository is empty" : "No files"}
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

export default SourceView
