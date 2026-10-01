import { Link as RouterLink } from "@tanstack/react-router"
import type { ReactNode } from "react"
import { Suspense } from "react"

import PendingItems from "@/components/Pending/PendingItems"

interface RepositoryLayoutProps {
  owner: string
  repo: string
  children: ReactNode
}

const RepositoryLayout = ({ owner, repo, children }: RepositoryLayoutProps) => (
  <div className="flex flex-col gap-6">
    <div>
      <h1 className="text-2xl font-bold tracking-tight">
        <RouterLink
          to="/$owner/$repo"
          params={{ owner, repo }}
          className="hover:underline"
        >
          {owner !== "_" && (
            <>
              {owner}
              <span className="text-muted-foreground font-normal"> / </span>
            </>
          )}
          {repo}
        </RouterLink>
      </h1>
    </div>
    <Suspense fallback={<PendingItems />}>{children}</Suspense>
  </div>
)

export default RepositoryLayout
