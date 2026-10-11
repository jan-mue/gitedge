import { useQuery } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { useState } from "react"
import { repositoriesGetBlameOptions } from "@/client/@tanstack/react-query.gen"
import RepoBreadcrumbs from "@/components/Repositories/RepoBreadcrumbs"
import SourceLink from "@/components/Repositories/SourceLink"
import RepositoryLoading, { RepositoryError } from "./RepositoryLoading"

const BlameView = ({
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
  if (isError)
    return (
      <RepositoryError
        message={typeof error?.detail === "string" ? error.detail : "Unable to load blame."}
        retry={() => refetch()}
      />
    )
  const mode = /^[0-9a-f]{40}$/.test(revision) ? "commit" : "branch"
  const groups = new Map<number, number>()
  for (let index = 0; index < data.lines.length; ) {
    let end = index + 1
    while (end < data.lines.length && data.lines[end].commit.sha === data.lines[index].commit.sha) end++
    groups.set(index, end - index)
    index = end
  }
  return (
    <div className="space-y-3">
      <RepoBreadcrumbs owner={owner} repo={repo} path={path} mode={mode} refName={revision} />
      <div className="overflow-hidden rounded-lg border bg-card">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b bg-secondary px-4 py-2 text-sm">
          <span className="text-muted-foreground">
            {data.lines.length} lines · Blame at {revision.slice(0, 12)}
          </span>
          <div className="flex items-center gap-2">
            <SourceLink
              owner={owner}
              repo={repo}
              mode={mode}
              refName={revision}
              path={path}
              className="rounded border bg-background px-2.5 py-1 text-xs hover:bg-accent"
            >
              Normal view
            </SourceLink>
            <Link
              to="/$owner/$repo/blame/$"
              params={{ owner, repo, _splat: path }}
              search={{ ref: data.revision }}
              className="rounded border bg-background px-2.5 py-1 text-xs hover:bg-accent"
            >
              Permalink
            </Link>
            <button
              type="button"
              onClick={() => setEscapedTabs((value) => !value)}
              className="rounded border bg-background px-2.5 py-1 text-xs hover:bg-accent"
            >
              {escapedTabs ? "Unescape tabs" : "Escape tabs"}
            </button>
          </div>
        </div>
        {data.lines.length ? (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <tbody>
                {data.lines.map((line, index) => (
                  <tr key={line.number} id={`L${line.number}`} className="align-top hover:bg-accent/30">
                    {groups.has(index) && (
                      <td
                        rowSpan={groups.get(index)}
                        className="w-72 min-w-64 border-r border-t bg-secondary/50 px-3 py-2"
                      >
                        <div className="flex items-start gap-2">
                          <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-accent text-xs">
                            {line.commit.author.slice(0, 1).toUpperCase()}
                          </span>
                          <div className="min-w-0">
                            <Link
                              to="/$owner/$repo/commit/$hash"
                              params={{ owner, repo, hash: line.commit.sha }}
                              className="block max-w-60 truncate text-xs hover:text-primary hover:underline"
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
                              className="font-mono text-xs text-primary hover:underline"
                            >
                              {line.commit.sha.slice(0, 10)}
                            </Link>
                          </div>
                        </div>
                      </td>
                    )}
                    <td className="w-14 select-none border-r px-3 text-right font-mono leading-6 text-muted-foreground">
                      <a href={`#L${line.number}`}>{line.number}</a>
                    </td>
                    <td className="whitespace-pre px-4 font-mono leading-6">
                      {escapedTabs ? line.content.replace(/\t/g, "\\t") : line.content}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="p-8 text-center text-sm text-muted-foreground">This file is empty.</p>
        )}
      </div>
    </div>
  )
}
export default BlameView
