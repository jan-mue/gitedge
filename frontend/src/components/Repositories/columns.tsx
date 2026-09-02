import { Link as RouterLink } from "@tanstack/react-router"
import type { ColumnDef } from "@tanstack/react-table"
import { Check, Copy, GitBranch } from "lucide-react"

import type { Repository } from "@/client"
import { Button } from "@/components/ui/button"
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard"

function CopyPath({ path }: { path: string }) {
  const [copiedText, copy] = useCopyToClipboard()
  const isCopied = copiedText === path

  return (
    <div className="flex items-center gap-1.5 group">
      <span className="font-mono text-xs text-muted-foreground">{path}</span>
      <Button
        variant="ghost"
        size="icon"
        className="size-6 opacity-0 group-hover:opacity-100 transition-opacity"
        onClick={(e) => {
          e.stopPropagation()
          copy(path)
        }}
      >
        {isCopied ? (
          <Check className="size-3 text-green-500" />
        ) : (
          <Copy className="size-3" />
        )}
        <span className="sr-only">Copy path</span>
      </Button>
    </div>
  )
}

function parseRepoPath(path: string): { owner: string; repo: string } {
  const cleaned = path.replace(/\.git$/, "")
  const parts = cleaned.split("/")
  if (parts.length === 1) {
    return { owner: "_", repo: parts[0] }
  }
  return {
    owner: parts[0] || "",
    repo: parts.slice(1).join("/") || parts[0] || "",
  }
}

export const columns: ColumnDef<Repository>[] = [
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => {
      const { owner, repo } = parseRepoPath(row.original.path)
      return (
        <RouterLink
          to="/$owner/$repo"
          params={{ owner, repo }}
          className="flex items-center gap-2 font-medium text-primary hover:underline"
          data-testid={`repo-link-${row.original.name}`}
        >
          <GitBranch className="h-4 w-4 text-muted-foreground" />
          {owner === "_" ? row.original.name : `${owner}/${row.original.name}`}
        </RouterLink>
      )
    },
  },
  {
    accessorKey: "path",
    header: "Clone Path",
    cell: ({ row }) => <CopyPath path={row.original.path} />,
  },
]
