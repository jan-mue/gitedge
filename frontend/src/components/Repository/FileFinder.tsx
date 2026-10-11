import { useQuery } from "@tanstack/react-query"
import { FileText, Search } from "lucide-react"
import { useState } from "react"
import { repositoriesGetFileIndexOptions } from "@/client/@tanstack/react-query.gen"
import type { SourceMode } from "@/components/Repositories/SourceLink"
import SourceLink from "@/components/Repositories/SourceLink"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import RepositoryLoading, { RepositoryError } from "./RepositoryLoading"

const FileFinder = ({
  owner,
  repo,
  revision,
  mode = "branch",
}: {
  owner: string
  repo: string
  revision: string
  mode?: SourceMode
}) => {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState("")
  const { data, isPending, isError, refetch } = useQuery({
    ...repositoriesGetFileIndexOptions({ path: { owner, repo }, query: { ref: revision } }),
    enabled: open,
    staleTime: 30_000,
  })
  const paths = data?.paths.filter((path) => path.toLowerCase().includes(search.toLowerCase())) ?? []
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button
          type="button"
          className="flex items-center gap-1.5 rounded border bg-secondary px-3 py-1.5 text-sm hover:bg-accent"
        >
          <Search className="size-3.5" />
          Find a file
        </button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Find a file</DialogTitle>
          <DialogDescription>Search files in {revision}.</DialogDescription>
        </DialogHeader>
        <Input
          aria-label="Search files"
          placeholder="Type a filename or path…"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <div className="max-h-80 overflow-y-auto">
          {isPending ? (
            <RepositoryLoading label="Loading files" rows={4} />
          ) : isError ? (
            <RepositoryError message="Unable to load files." retry={() => refetch()} />
          ) : paths.length ? (
            <>
              {paths.slice(0, 100).map((path) => (
                <SourceLink
                  key={path}
                  owner={owner}
                  repo={repo}
                  mode={mode}
                  refName={revision}
                  path={path}
                  onClick={() => setOpen(false)}
                  className="flex items-center gap-2 rounded px-3 py-2 text-sm hover:bg-accent"
                >
                  <FileText className="size-4 shrink-0 text-muted-foreground" />
                  <span className="break-all">{path}</span>
                </SourceLink>
              ))}
              {paths.length > 100 && (
                <p className="p-3 text-xs text-muted-foreground">
                  Showing 100 of {paths.length} files. Refine your search to see more.
                </p>
              )}
            </>
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">
              {search ? "No matching files." : "This revision has no files."}
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
export default FileFinder
