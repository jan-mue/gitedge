import { useQuery } from "@tanstack/react-query"
import { Link as RouterLink, useParams } from "@tanstack/react-router"
import { ArrowLeft, GitCommitHorizontal } from "lucide-react"
import type { CommitFileChange } from "@/client"
import { repositoriesGetCommitOptions } from "@/client/@tanstack/react-query.gen"
import RepositoryLoading, { RepositoryError } from "@/components/Repository/RepositoryLoading"

const changeBadge: Record<string, string> = {
  add: "bg-success/15 text-success",
  delete: "bg-destructive/15 text-destructive",
  rename: "bg-info/15 text-info",
  modify: "bg-muted text-muted-foreground",
}

const changeLabel: Record<string, string> = {
  add: "Added",
  delete: "Deleted",
  rename: "Renamed",
  modify: "Modified",
}

const DiffHunk = ({ patch }: { patch: string }) => {
  const lines = patch.split("\n")
  const start = lines.findIndex((line) => line.startsWith("@@"))
  const hunkLines = start === -1 ? [] : lines.slice(start)

  if (hunkLines.length === 0) {
    return <div className="px-4 py-4 text-xs text-muted-foreground">Binary file or no textual changes.</div>
  }

  return (
    <pre className="overflow-x-auto py-1 text-xs leading-relaxed">
      {hunkLines.map((line, index) => {
        let className = "px-4"
        if (line.startsWith("@@")) {
          className += " bg-primary/5 text-primary"
        } else if (line.startsWith("+")) {
          className += " bg-success/10 text-foreground"
        } else if (line.startsWith("-")) {
          className += " bg-destructive/10 text-foreground"
        } else {
          className += " text-muted-foreground"
        }
        return (
          <div key={index} className={className}>
            {line || " "}
          </div>
        )
      })}
    </pre>
  )
}

const FileDiff = ({ file }: { file: CommitFileChange }) => (
  <div className="overflow-hidden rounded-lg border border-border bg-card" data-testid={`commit-file-${file.path}`}>
    <div className="flex flex-wrap items-center gap-2 border-b border-border bg-secondary px-4 py-2">
      <span className="font-mono text-sm text-foreground">{file.path}</span>
      <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${changeBadge[file.change_type] ?? ""}`}>
        {changeLabel[file.change_type] ?? file.change_type}
      </span>
      <span className="ml-auto flex items-center gap-2 font-mono text-xs">
        <span className="text-success">+{file.additions}</span>
        <span className="text-destructive">-{file.deletions}</span>
      </span>
    </div>
    <DiffHunk patch={file.patch} />
  </div>
)

const CommitDetail = () => {
  const { owner, repo, hash } = useParams({ from: "/_layout/$owner/$repo/commit/$hash" })

  const {
    data: commit,
    isPending,
    isError,
    refetch,
  } = useQuery({
    ...repositoriesGetCommitOptions({ path: { owner, repo, sha: hash } }),
  })

  if (isPending) return <RepositoryLoading label="Loading commit" />
  if (isError || !commit) return <RepositoryError message="Unable to load commit." retry={() => refetch()} />

  const [title, ...bodyLines] = commit.message.split("\n")
  const body = bodyLines.join("\n").trim()

  return (
    <div className="space-y-4" data-testid="commit-detail">
      <RouterLink
        to="/$owner/$repo/commits"
        params={{ owner, repo }}
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to commits
      </RouterLink>

      <div className="rounded-lg border border-border bg-card px-4 py-4">
        <h1 className="text-lg font-semibold text-foreground">{title}</h1>
        {body && <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">{body}</p>}
        <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <GitCommitHorizontal className="h-4 w-4" />
            <span className="font-mono text-foreground" data-testid="commit-sha">
              {commit.sha}
            </span>
          </span>
          <span>
            <span className="font-medium text-foreground">{commit.author}</span>
            {commit.author_email && ` <${commit.author_email}>`} committed{" "}
            {new Date(commit.timestamp * 1000).toLocaleString()}
          </span>
        </div>
        {commit.parents.length > 0 && (
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span>Parent{commit.parents.length > 1 ? "s" : ""}:</span>
            {commit.parents.map((parent) => (
              <RouterLink
                key={parent}
                to="/$owner/$repo/commit/$hash"
                params={{ owner, repo, hash: parent }}
                className="font-mono text-primary hover:underline"
              >
                {parent.slice(0, 10)}
              </RouterLink>
            ))}
          </div>
        )}
      </div>

      <div className="flex items-center gap-4 text-sm text-muted-foreground">
        <span className="font-medium text-foreground">
          {commit.files.length} {commit.files.length === 1 ? "file" : "files"} changed
        </span>
        <span className="font-mono text-success">+{commit.additions}</span>
        <span className="font-mono text-destructive">-{commit.deletions}</span>
      </div>

      <div className="space-y-4">
        {commit.files.map((file) => (
          <FileDiff key={file.path} file={file} />
        ))}
      </div>
    </div>
  )
}

export default CommitDetail
