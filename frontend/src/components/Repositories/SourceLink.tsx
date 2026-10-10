import { Link as RouterLink } from "@tanstack/react-router"
import type { ReactNode } from "react"

export type SourceMode = "branch" | "commit"

interface SourceLinkProps {
  owner: string
  repo: string
  mode: SourceMode
  /** Branch name or commit SHA, depending on the mode. */
  refName: string
  /** Path within the repository, relative to the repo root. */
  path: string
  onClick?: () => void
  className?: string
  "data-testid"?: string
  children: ReactNode
}

const SourceLink = ({
  owner,
  repo,
  mode,
  refName,
  path,
  className,
  onClick,
  "data-testid": testId,
  children,
}: SourceLinkProps) => {
  if (mode === "commit") {
    return (
      <RouterLink
        to={path ? "/$owner/$repo/src/commit/$sha/$" : "/$owner/$repo/src/commit/$sha"}
        params={{ owner, repo, sha: refName, _splat: path }}
        onClick={onClick}
        className={className}
        data-testid={testId}
      >
        {children}
      </RouterLink>
    )
  }

  return (
    <RouterLink
      to={path ? "/$owner/$repo/src/branch/$branch/$" : "/$owner/$repo/src/branch/$branch"}
      params={{ owner, repo, branch: refName, _splat: path }}
      onClick={onClick}
      className={className}
      data-testid={testId}
    >
      {children}
    </RouterLink>
  )
}

export default SourceLink
