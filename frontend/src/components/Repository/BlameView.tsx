import { useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { repositoriesGetBlameOptions } from "@/client/@tanstack/react-query.gen"
import { Button, ExternalLink, Link } from "@/components/design-system"
import RepoBreadcrumbs from "@/components/Repositories/RepoBreadcrumbs"
import SourceLink from "@/components/Repositories/SourceLink"
import RepositoryLoading, { RepositoryError } from "./RepositoryLoading"

const blameGroups = (lines: { commit: { sha: string } }[]) => {
  const groups = new Map<number, number>()
  for (let index = 0; index < lines.length; ) {
    let end = index + 1
    while (end < lines.length && lines[end].commit.sha === lines[index].commit.sha) end++
    groups.set(index, end - index)
    index = end
  }
  return groups
}
const blameError = (error: { detail?: unknown }) =>
  typeof error?.detail === "string" ? error.detail : "Unable to load blame."
export const BlameView = ({
  owner,
  repo,
  revision,
  path,
}: {
  owner: string
  repo: string
  revision: string
  path: string
}) => {
  const [escapedTabs, setEscapedTabs] = useState(false)
  const { data, isPending, isError, error, refetch } = useQuery({
    ...repositoriesGetBlameOptions({ path: { owner, repo }, query: { ref: revision, file_path: path } }),
    retry: false,
  })
  if (isPending) return <RepositoryLoading label="Loading blame" rows={12} />
  if (isError) return <RepositoryError message={blameError(error)} retry={() => refetch()} />
  const mode = /^[0-9a-f]{40}$/.test(revision) ? "commit" : "branch"
  const groups = blameGroups(data.lines)
  const renderLines = () => (
    <table className="w-full border-collapse text-sm">
      <tbody>
        {data.lines.map((line, index) => (
          <tr key={line.number} id={`L${line.number}`} className="align-top hover:bg-accent/30">
            {groups.has(index) && (
              <td rowSpan={groups.get(index)} className="w-72 min-w-64 border-r border-t bg-secondary/50 px-3 py-2">
                <div className="flex items-start gap-2">
                  <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-accent text-xs">
                    {line.commit.author.slice(0, 1).toUpperCase()}
                  </span>
                  <div className="min-w-0">
                    <Link
                      to="/$owner/$repo/commit/$hash"
                      params={{ owner, repo, hash: line.commit.sha }}
                      appearance="commitPreview"
                      title={line.commit.message}
                    >
                      {line.commit.message.split("\n")[0]}
                    </Link>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {line.commit.author} · {new Date(line.commit.timestamp * 1000).toLocaleDateString()}
                    </p>
                    <Link
                      to="/$owner/$repo/commit/$hash"
                      params={{ owner, repo, hash: line.commit.sha }}
                      appearance="hash"
                    >
                      {line.commit.sha.slice(0, 10)}
                    </Link>
                  </div>
                </div>
              </td>
            )}
            <td className="w-14 select-none border-r px-3 text-right font-mono leading-6 text-muted-foreground">
              <ExternalLink href={`#L${line.number}`} appearance="inherited">
                {line.number}
              </ExternalLink>
            </td>
            <td className="whitespace-pre px-4 font-mono leading-6">
              {escapedTabs ? line.content.replace(/\t/g, "\\t") : line.content}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )

  return (
    <div className="space-y-3">
      <RepoBreadcrumbs owner={owner} repo={repo} path={path} mode={mode} refName={revision} />
      <div className="overflow-hidden rounded-lg border bg-card">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b bg-secondary px-4 py-2 text-sm">
          <span className="text-muted-foreground">
            {data.lines.length} lines · Blame at {revision.slice(0, 12)}
          </span>
          <div className="flex items-center gap-2">
            <SourceLink owner={owner} repo={repo} mode={mode} refName={revision} path={path} appearance="codeAction">
              Normal view
            </SourceLink>
            <Link
              to="/$owner/$repo/blame/$"
              params={{ owner, repo, _splat: path }}
              search={{ ref: data.revision }}
              appearance="codeAction"
            >
              Permalink
            </Link>
            <Button type="button" onClick={() => setEscapedTabs((value) => !value)} variant="codeAction" size="code">
              {escapedTabs ? "Unescape tabs" : "Escape tabs"}
            </Button>
          </div>
        </div>
        {data.lines.length ? (
          <div className="overflow-x-auto">{renderLines()}</div>
        ) : (
          <p className="p-8 text-center text-sm text-muted-foreground">This file is empty.</p>
        )}
      </div>
    </div>
  )
}
