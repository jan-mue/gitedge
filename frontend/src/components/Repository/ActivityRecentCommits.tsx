import { Link } from "@tanstack/react-router"
import { GitCommit } from "lucide-react"

import type { CommitListItem } from "@/client"

interface ActivityRecentCommitsProps {
  commits: CommitListItem[]
  owner: string
  repo: string
}

const ActivityRecentCommits = ({ commits, owner, repo }: ActivityRecentCommitsProps) => (
  <div className="space-y-4">
    <h2 className="text-lg font-medium text-foreground">Recent commits</h2>
    <div className="overflow-hidden rounded-lg border border-border">
      {commits.map((commit, index) => (
        <div
          key={commit.sha}
          className={`flex flex-col justify-between gap-2 px-4 py-3 sm:flex-row sm:items-center ${index < commits.length - 1 ? "border-b border-border" : ""}`}
        >
          <div className="flex min-w-0 items-center gap-3">
            <GitCommit aria-hidden="true" className="h-4 w-4 shrink-0 text-muted-foreground" />
            <div className="min-w-0">
              <Link
                to="/$owner/$repo/commit/$hash"
                params={{ owner, repo, hash: commit.sha }}
                className="block truncate text-sm text-foreground hover:text-primary"
                title={commit.message.split("\n")[0]}
              >
                {commit.message.split("\n")[0]}
              </Link>
              <span className="text-xs text-muted-foreground">
                {commit.author} ·{" "}
                <time dateTime={new Date(commit.timestamp * 1000).toISOString()}>
                  {new Date(commit.timestamp * 1000).toLocaleString()}
                </time>
              </span>
            </div>
          </div>
          <Link
            to="/$owner/$repo/commit/$hash"
            params={{ owner, repo, hash: commit.sha }}
            className="shrink-0 self-start sm:self-auto"
            aria-label={`View commit ${commit.sha.slice(0, 7)}`}
          >
            <code className="rounded border border-border bg-secondary px-2 py-0.5 font-mono text-xs text-foreground hover:text-primary">
              {commit.sha.slice(0, 7)}
            </code>
          </Link>
        </div>
      ))}
      {!commits.length && <p className="py-12 text-center text-sm text-muted-foreground">No commits yet.</p>}
    </div>
  </div>
)

export default ActivityRecentCommits
