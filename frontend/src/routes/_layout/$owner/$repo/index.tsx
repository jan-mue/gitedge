import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { File, Folder } from "lucide-react"

import type { TreeEntry } from "@/client"
import { RepositoriesService } from "@/client"
import RefBadge from "@/components/Repositories/RefBadge"
import RepoBreadcrumbs from "@/components/Repositories/RepoBreadcrumbs"
import RepositoryLayout from "@/components/Repositories/RepositoryLayout"
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table"
import { formatSize } from "@/utils"

interface SearchParams {
  ref?: string
  path?: string
}

export const Route = createFileRoute("/_layout/$owner/$repo/")({
  component: RepositoryTree,
  validateSearch: (search: Record<string, unknown>): SearchParams => ({
    ref: (search.ref as string) || undefined,
    path: (search.path as string) || undefined,
  }),
  head: ({ params }) => ({
    meta: [
      {
        title: `${params.owner}/${params.repo} - GitEdge`,
      },
    ],
  }),
})

function TreeEntryRow({
  entry,
  owner,
  repo,
  searchRef,
}: {
  entry: TreeEntry
  owner: string
  repo: string
  searchRef?: string
}) {
  const navigate = useNavigate()
  const isDir = entry.type === "tree"

  const handleClick = () => {
    if (isDir) {
      navigate({
        to: "/$owner/$repo",
        params: { owner, repo },
        search: { ref: searchRef, path: entry.path },
      })
    } else {
      navigate({
        to: "/$owner/$repo/blob",
        params: { owner, repo },
        search: { ref: searchRef, path: entry.path },
      })
    }
  }

  return (
    <TableRow
      className="cursor-pointer"
      onClick={handleClick}
      data-testid={`tree-entry-${entry.name}`}
    >
      <TableCell className="w-8">
        {isDir ? (
          <Folder className="h-4 w-4 text-blue-500" />
        ) : (
          <File className="h-4 w-4 text-muted-foreground" />
        )}
      </TableCell>
      <TableCell>
        <span
          className={
            isDir
              ? "text-primary hover:underline font-medium"
              : "hover:underline"
          }
        >
          {entry.name}
        </span>
      </TableCell>
      <TableCell className="text-right text-muted-foreground text-sm w-24">
        {entry.size != null ? formatSize(entry.size) : ""}
      </TableCell>
    </TableRow>
  )
}

function ParentDirectoryRow({
  owner,
  repo,
  treePath,
  searchRef,
}: {
  owner: string
  repo: string
  treePath: string
  searchRef?: string
}) {
  const navigate = useNavigate()
  const parentPath = treePath.split("/").slice(0, -1).join("/")

  return (
    <TableRow
      className="cursor-pointer"
      onClick={() => {
        navigate({
          to: "/$owner/$repo",
          params: { owner, repo },
          search: {
            ref: searchRef,
            path: parentPath || undefined,
          },
        })
      }}
      data-testid="tree-entry-parent"
    >
      <TableCell className="w-8">
        <Folder className="h-4 w-4 text-blue-500" />
      </TableCell>
      <TableCell>
        <span className="text-primary hover:underline">..</span>
      </TableCell>
      <TableCell className="w-24" />
    </TableRow>
  )
}

function TreeContent() {
  const { owner, repo } = Route.useParams()
  const { ref: searchRef, path: treePath } = Route.useSearch()
  const repoPath = owner === "_" ? `${repo}.git` : `${owner}/${repo}.git`

  const { data: tree } = useSuspenseQuery({
    queryKey: ["tree", repoPath, searchRef ?? "main", treePath ?? ""],
    queryFn: async () =>
      (
        await RepositoriesService.getTree({
          path: { path: repoPath },
          query: { ref: searchRef, tree_path: treePath },
        })
      ).data,
  })

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <RepoBreadcrumbs
          owner={owner}
          repo={repo}
          path={treePath ?? ""}
          searchRef={searchRef}
        />
        <RefBadge gitRef={tree.ref} data-testid="current-ref" />
      </div>

      <div className="border rounded-lg" data-testid="file-tree">
        <Table>
          <TableBody>
            {treePath && (
              <ParentDirectoryRow
                owner={owner}
                repo={repo}
                treePath={treePath}
                searchRef={searchRef}
              />
            )}
            {tree.entries.map((entry) => (
              <TreeEntryRow
                key={entry.path}
                entry={entry}
                owner={owner}
                repo={repo}
                searchRef={searchRef}
              />
            ))}
            {tree.entries.length === 0 && !treePath && (
              <TableRow>
                <TableCell
                  colSpan={3}
                  className="text-center text-muted-foreground py-8"
                >
                  This repository is empty
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

function RepositoryTree() {
  const { owner, repo } = Route.useParams()

  return (
    <RepositoryLayout owner={owner} repo={repo}>
      <TreeContent />
    </RepositoryLayout>
  )
}
