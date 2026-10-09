import type { SourceMode } from "@/components/Repositories/SourceLink"
import SourceLink from "@/components/Repositories/SourceLink"

interface RepoBreadcrumbsProps {
  owner: string
  repo: string
  /** Full path segments (e.g. "src/lib/utils.ts"). Empty for repo root. */
  path: string
  mode?: SourceMode
  /** Branch name or commit SHA, depending on the mode. */
  refName?: string
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
  mode = "branch",
  refName = "main",
  lastSegmentIsStatic = true,
}: RepoBreadcrumbsProps) => {
  const parts = path ? path.split("/").filter(Boolean) : []

  return (
    <div className="flex items-center gap-1 text-sm flex-wrap">
      <SourceLink
        owner={owner}
        repo={repo}
        mode={mode}
        refName={refName}
        path=""
        className="font-semibold text-primary hover:underline"
      >
        {repo}
      </SourceLink>
      {parts.map((part, i) => {
        const subPath = parts.slice(0, i + 1).join("/")
        const isLast = i === parts.length - 1

        return (
          <span key={subPath} className="flex items-center gap-1">
            <span className="text-muted-foreground">/</span>
            {isLast && lastSegmentIsStatic ? (
              <span className="font-medium">{part}</span>
            ) : (
              <SourceLink
                owner={owner}
                repo={repo}
                mode={mode}
                refName={refName}
                path={subPath}
                className="text-primary hover:underline"
              >
                {part}
              </SourceLink>
            )}
          </span>
        )
      })}
    </div>
  )
}

export default RepoBreadcrumbs
