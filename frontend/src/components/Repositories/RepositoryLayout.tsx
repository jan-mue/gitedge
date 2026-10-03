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
  <div className="-mx-6 md:-mx-8 -mt-6 md:-mt-8 flex flex-col">
    <RepoHeader owner={owner} repo={repo} />
    <div className="px-6 md:px-8 py-6">
      <div className="mx-auto max-w-7xl">
        <Suspense fallback={<PendingItems />}>{children}</Suspense>
      </div>
    </div>
  </div>
)

export default RepositoryLayout
