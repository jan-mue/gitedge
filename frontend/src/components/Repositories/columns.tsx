import type { ColumnDef } from "@tanstack/react-table"
import { Check, Copy, GitBranch } from "lucide-react"
import type { Repository } from "@/client"
import type { DataTableFeatures } from "@/components/Common/DataTable"
import { Button, Link as RouterLink } from "@/components/design-system"
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard"

function CopyPath({ path }: { path: string }) {
  const [copiedText, copy] = useCopyToClipboard()
  const isCopied = copiedText === path

  return (
    <div className="flex items-center gap-1.5 group">
      <span className="font-mono text-xs text-muted-foreground">{path}</span>
      <Button
        variant="ghost"
        size="icon-xs"
        reveal
        onClick={(e) => {
          e.stopPropagation()
          copy(path)
        }}
      >
        {isCopied ? <Check className="size-3 text-success" /> : <Copy className="size-3" />}
        <span className="sr-only">Copy path</span>
      </Button>
    </div>
  )
}

export const columns: ColumnDef<DataTableFeatures, Repository>[] = [
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => (
      <RouterLink
        to="/$owner/$repo"
        params={{ owner: row.original.owner, repo: row.original.name }}
        appearance="repositoryEntry"
        data-testid={`repo-link-${row.original.name}`}
      >
        <GitBranch className="h-4 w-4 text-muted-foreground" />
        {row.original.owner}/{row.original.name}
      </RouterLink>
    ),
  },
  {
    accessorKey: "name",
    id: "clonePath",
    header: "Clone Path",
    cell: ({ row }) => <CopyPath path={`${row.original.owner}/${row.original.name}.git`} />,
  },
]

export const RepositorySummary = ({ repo }: { repo: Repository }) => {
  return (
    <div className="min-w-0 flex-1">
      <RouterLink to="/$owner/$repo" params={{ owner: repo.owner, repo: repo.name }} appearance="repository">
        {repo.owner}/{repo.name}
      </RouterLink>
      {repo.description && <p className="text-xs text-muted-foreground mt-1">{repo.description}</p>}
    </div>
  )
}
