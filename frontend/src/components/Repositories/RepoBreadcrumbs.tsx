import { Link as RouterLink } from "@tanstack/react-router"

interface RepoBreadcrumbsProps {
  owner: string
  repo: string
  /** Full path segments (e.g. "src/lib/utils.ts"). Empty for repo root. */
  path: string
  searchRef?: string
  /**
   * When true, the last segment is rendered as plain text (current file/dir).
   * When false, all segments are links (useful in tree view where the last
   * segment is the current directory).
   */
  lastSegmentIsStatic?: boolean
}

const RepoBreadcrumbs = ({
  owner,
  repo,
  path,
  searchRef,
  lastSegmentIsStatic = true,
}: RepoBreadcrumbsProps) => {
  const parts = path ? path.split("/").filter(Boolean) : []

  return (
    <div className="flex items-center gap-1 text-sm flex-wrap">
      <RouterLink
        to="/$owner/$repo"
        params={{ owner, repo }}
        search={{ ref: searchRef }}
        className="font-semibold text-primary hover:underline"
      >
        {repo}
      </RouterLink>
      {parts.map((part, i) => {
        const subPath = parts.slice(0, i + 1).join("/")
        const isLast = i === parts.length - 1

        return (
          <span key={subPath} className="flex items-center gap-1">
            <span className="text-muted-foreground">/</span>
            {isLast && lastSegmentIsStatic ? (
              <span className="font-medium">{part}</span>
            ) : (
              <RouterLink
                to="/$owner/$repo"
                params={{ owner, repo }}
                search={{ ref: searchRef, path: subPath }}
                className="text-primary hover:underline"
              >
                {part}
              </RouterLink>
            )}
          </span>
        )
      })}
    </div>
  )
}

export default RepoBreadcrumbs
