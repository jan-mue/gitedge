import { useQuery } from "@tanstack/react-query"
import { useParams } from "@tanstack/react-router"
import { ArrowLeft, GitCommitHorizontal } from "lucide-react"
import { repositoriesGetCommitOptions } from "@/client/@tanstack/react-query.gen"
import { Link as RouterLink } from "@/components/design-system"
import { DiffViewer } from "@/components/Repository/DiffViewer"
import RepositoryLoading, { RepositoryError } from "@/components/Repository/RepositoryLoading"

export const CommitDetail = () => {
  const { owner, repo, hash } = useParams({ from: "/_layout/$owner/$repo/commit/$hash" })

  const {
    data: commit,
    isPending,
    isError,
    refetch,
  } = useQuery({
    ...repositoriesGetCommitOptions({ path: { owner, repo, sha: hash }, query: { include_diff: false } }),
  })

  if (isPending) return <RepositoryLoading label="Loading commit" />
  if (isError || !commit) return <RepositoryError message="Unable to load commit." retry={() => refetch()} />

  const [title, ...bodyLines] = commit.message.split("\n")
  const body = bodyLines.join("\n").trim()
  const renderMetadata = () => {
    const renderParents = () =>
      commit.parents.length > 0 && (
        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span>Parent{commit.parents.length > 1 ? "s" : ""}:</span>
          {commit.parents.map((parent) => (
            <RouterLink
              key={parent}
              to="/$owner/$repo/commit/$hash"
              params={{ owner, repo, hash: parent }}
              appearance="revision"
            >
              {parent.slice(0, 10)}
            </RouterLink>
          ))}
        </div>
      )

    return (
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
        {renderParents()}
      </div>
    )
  }

  return (
    <div className="space-y-4" data-testid="commit-detail">
      <RouterLink to="/$owner/$repo/commits" params={{ owner, repo }} appearance="muted">
        <ArrowLeft className="h-4 w-4" />
        Back to commits
      </RouterLink>

      {renderMetadata()}

      <RouterLink
        to="/$owner/$repo/compare"
        params={{ owner, repo }}
        search={{ base: commit.parents[0] ?? commit.sha, head: commit.sha }}
        appearance="muted"
      >
        Compare revisions
      </RouterLink>
      <DiffViewer
        diffSource={{ owner, repo, base: commit.parents[0] ?? "", head: commit.sha }}
        files={commit.files}
        additions={commit.additions}
        deletions={commit.deletions}
      />
    </div>
  )
}
