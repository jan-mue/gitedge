import { useMatches, useSearch } from "@tanstack/react-router"
import type { ReactNode } from "react"
import { Suspense } from "react"
import { NotificationReturnBanner } from "@/components/Notifications/NotificationReturnBanner"
import RepoHeader from "@/components/Repository/RepoHeader"
import RepositoryLoading from "@/components/Repository/RepositoryLoading"

interface RepositoryLayoutProps {
  owner: string
  repo: string
  children: ReactNode
}

const RepositoryLayout = ({ owner, repo, children }: RepositoryLayoutProps) => {
  const search = useSearch({ strict: false })
  const matches = useMatches()
  const path = matches[matches.length - 1]?.fullPath ?? ""
  const discussion = path.endsWith("/issues/$number") || path.endsWith("/pulls/$number")
  return (
    <div className="flex flex-col">
      <RepoHeader owner={owner} repo={repo} />
      <main className="container mx-auto max-w-7xl px-4 py-6">
        {search.from === "notifications" && (
          <div className={discussion ? "max-w-4xl mx-auto mb-6" : "mb-6"}>
            <NotificationReturnBanner />
          </div>
        )}
        <Suspense fallback={<RepositoryLoading />}>{children}</Suspense>
      </main>
    </div>
  )
}

export default RepositoryLayout
