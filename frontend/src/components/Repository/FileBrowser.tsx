import { FileText, Folder } from "lucide-react"
import type { CommitInfo, TreeEntry } from "@/client"
import { FileRow, Link } from "@/components/design-system"
import SourceLink, { type SourceMode } from "@/components/Repositories/SourceLink"
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
        <FileRow>
          <SourceLink
            owner={owner}
            repo={repo}
            mode={mode}
            refName={refName}
            path={treePath.split("/").slice(0, -1).join("/")}
            appearance="fileEntry"
            data-testid="tree-entry-parent"
          >
            <Folder aria-hidden="true" className="size-4 shrink-0 text-primary" />
            <span>..</span>
          </SourceLink>
        </FileRow>
      )}

      {entries.map((entry) => (
        <FileRow key={entry.path} data-testid={`file-row-${entry.name}`}>
          <SourceLink
            owner={owner}
            repo={repo}
            mode={mode}
            refName={refName}
            path={entry.path}
            appearance="fileEntry"
            data-testid={`tree-entry-${entry.name}`}
          >
            {entry.type === "tree" ? (
              <Folder aria-hidden="true" className="size-4 shrink-0 text-primary" />
            ) : (
              <FileText aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
            )}
            <span className="truncate" title={entry.name}>
              {entry.name}
            </span>
          </SourceLink>
          {entry.last_commit ? (
            <Link
              to="/$owner/$repo/commit/$hash"
              params={{ owner, repo, hash: entry.last_commit.sha }}
              appearance="fileCommit"
              title={entry.last_commit.message}
              data-testid={`entry-commit-${entry.name}`}
            >
              {entry.last_commit.message.split("\n")[0]}
            </Link>
          ) : (
            <span className="order-last col-span-2 text-sm text-muted-foreground sm:order-none sm:col-span-1">
              Commit information unavailable
            </span>
          )}
          {entry.last_commit && (
            <time
              className="whitespace-nowrap text-xs text-muted-foreground sm:text-sm"
              dateTime={new Date(entry.last_commit.timestamp * 1000).toISOString()}
              title={new Date(entry.last_commit.timestamp * 1000).toLocaleString()}
            >
              {formatRelativeTime(entry.last_commit.timestamp)}
            </time>
          )}
        </FileRow>
      ))}

      {entries.length === 0 && !treePath && (
        <div className="text-center text-muted-foreground py-8 text-sm">This repository is empty</div>
      )}
    </div>
  )
}

export default FileBrowser
