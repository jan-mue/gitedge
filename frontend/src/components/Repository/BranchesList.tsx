import { useQuery } from "@tanstack/react-query"
import { GitBranch, Tag } from "lucide-react"

import { releasesListTagsOptions, repositoriesListBranchesOptions } from "@/client/@tanstack/react-query.gen"

interface BranchesListProps {
  owner: string
  repo: string
}

const BranchesList = ({ owner, repo }: BranchesListProps) => {
  const { data: branches } = useQuery({
    ...repositoriesListBranchesOptions({ path: { owner, repo } }),
  })

  const { data: tagsData } = useQuery({
    ...releasesListTagsOptions({ path: { owner, repo } }),
  })

  const tags = tagsData?.data ?? []

  return (
    <div className="space-y-6" data-testid="branches-list">
      <section className="border border-border rounded-lg overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-2.5 bg-secondary border-b border-border">
          <GitBranch className="w-4 h-4 text-muted-foreground" />
          <h2 className="text-sm font-semibold text-foreground">
            {branches?.length ?? 0} {branches?.length === 1 ? "branch" : "branches"}
          </h2>
        </div>
        {branches && branches.length > 0 ? (
          branches.map((branch) => (
            <div
              key={branch.name}
              className="flex items-center justify-between px-4 py-3 border-b border-border last:border-b-0"
            >
              <span className="font-mono text-sm text-foreground">{branch.name}</span>
              {branch.is_default && (
                <span className="text-xs px-2 py-0.5 rounded bg-secondary text-muted-foreground">default</span>
              )}
            </div>
          ))
        ) : (
          <div className="px-4 py-6 text-sm text-muted-foreground">No branches yet.</div>
        )}
      </section>

      <section className="border border-border rounded-lg overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-2.5 bg-secondary border-b border-border">
          <Tag className="w-4 h-4 text-muted-foreground" />
          <h2 className="text-sm font-semibold text-foreground">
            {tags.length} {tags.length === 1 ? "tag" : "tags"}
          </h2>
        </div>
        {tags.length > 0 ? (
          tags.map((tag) => (
            <div
              key={tag.name}
              className="flex items-center justify-between px-4 py-3 border-b border-border last:border-b-0"
            >
              <span className="font-mono text-sm text-foreground">{tag.name}</span>
              <span className="font-mono text-xs text-muted-foreground">{tag.commit_sha.slice(0, 10)}</span>
            </div>
          ))
        ) : (
          <div className="px-4 py-6 text-sm text-muted-foreground">No tags yet.</div>
        )}
      </section>
    </div>
  )
}

export default BranchesList
