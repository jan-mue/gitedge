import { useNavigate } from "@tanstack/react-router"
import { FileText, Folder } from "lucide-react"
import type { CommitInfo, TreeEntry } from "@/client"
import { Button } from "@/components/design-system"
import type { SourceMode } from "@/components/Repositories/SourceLink"
import { formatRelativeTime } from "@/utils"
import RepositoryCommitHeader from "./RepositoryCommitHeader"

interface FileBrowserProps {
  entries: TreeEntry[]
  owner: string
  repo: string
  mode?: SourceMode
  /** Branch name or commit SHA, depending on the mode. */
  refName?: string
  treePath?: string
  lastCommit?: CommitInfo | null
  lastCommitLoading?: boolean
  lastCommitError?: boolean
  onRetryLastCommit?: () => void
}

const FileBrowser = ({
  entries,
  owner,
  repo,
  mode = "branch",
  refName = "main",
  treePath,
  lastCommit,
  lastCommitLoading,
  lastCommitError,
  onRetryLastCommit,
}: FileBrowserProps) => {
  const navigate = useNavigate()

  const navigateToPath = (targetPath: string) => {
    if (mode === "commit") {
      navigate({ to: "/$owner/$repo/src/commit/$sha/$", params: { owner, repo, sha: refName, _splat: targetPath } })
    } else if (mode === "tag") {
      navigate({ to: "/$owner/$repo/src/tag/$tag/$", params: { owner, repo, tag: refName, _splat: targetPath } })
    } else {
      navigate({
        to: "/$owner/$repo/src/branch/$branch/$",
        params: { owner, repo, branch: refName, _splat: targetPath },
      })
    }
  }

  const handleEntryClick = (entry: TreeEntry) => {
    navigateToPath(entry.path)
  }

  const handleParentClick = () => {
    const parentPath = treePath?.split("/").slice(0, -1).join("/")
    navigateToPath(parentPath ?? "")
  }

  return (
    <div className="border border-border rounded-lg overflow-hidden" data-testid="file-tree">
      <RepositoryCommitHeader
        owner={owner}
        repo={repo}
        commit={lastCommit}
        loading={lastCommitLoading}
        error={lastCommitError}
        onRetry={onRetryLastCommit}
      />

      {treePath && (
        <Button type="button" onClick={handleParentClick} variant="row" size="file-row" data-testid="tree-entry-parent">
          <Folder className="w-4 h-4 text-primary flex-shrink-0" />
          <span>..</span>
        </Button>
      )}

      {entries.map((entry) => (
        <Button
          key={entry.path}
          type="button"
          onClick={() => handleEntryClick(entry)}
          variant="fileRow"
          size="file-row"
          data-testid={`tree-entry-${entry.name}`}
        >
          <span className="flex min-w-0 items-center gap-3">
            {entry.type === "tree" ? (
              <Folder className="size-4 shrink-0 text-primary" />
            ) : (
              <FileText className="size-4 shrink-0 text-muted-foreground" />
            )}
            <span data-slot="file-name" className="truncate" title={entry.name}>
              {entry.name}
            </span>
          </span>
          <span
            className="order-last col-span-2 min-w-0 truncate text-sm text-muted-foreground sm:order-none sm:col-span-1"
            title={entry.last_commit?.message}
            data-testid={`entry-commit-${entry.name}`}
          >
            {entry.last_commit?.message.split("\n")[0] ?? "Commit information unavailable"}
          </span>
          {entry.last_commit && (
            <time
              className="whitespace-nowrap text-xs text-muted-foreground sm:text-sm"
              dateTime={new Date(entry.last_commit.timestamp * 1000).toISOString()}
              title={new Date(entry.last_commit.timestamp * 1000).toLocaleString()}
            >
              {formatRelativeTime(entry.last_commit.timestamp)}
            </time>
          )}
        </Button>
      ))}

      {entries.length === 0 && !treePath && (
        <div className="text-center text-muted-foreground py-8 text-sm">This repository is empty</div>
      )}
    </div>
  )
}

export default FileBrowser
