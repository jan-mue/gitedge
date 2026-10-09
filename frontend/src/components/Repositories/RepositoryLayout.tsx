import type { ReactNode } from "react"
import { Suspense } from "react"

import PendingItems from "@/components/Pending/PendingItems"
import RepoHeader from "@/components/Repository/RepoHeader"

interface RepositoryLayoutProps {
  owner: string
  repo: string
  children: ReactNode
}

const RepositoryLayout = ({ owner, repo, children }: RepositoryLayoutProps) => (
  <div className="flex flex-col">
    <RepoHeader owner={owner} repo={repo} />
    <main className="container mx-auto max-w-7xl px-4 py-6">
      <Suspense fallback={<PendingItems />}>{children}</Suspense>
    </main>
  </div>
)

export default RepositoryLayout
