import { FileText, Folder } from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"
import RepositoryLoading from "./RepositoryLoading"

const widths = ["w-48", "w-64", "w-36", "w-56", "w-32", "w-72", "w-44", "w-60"]

const SourceLoading = ({ kind }: { kind?: "tree" | "blob" }) => {
  if (kind === "tree") return <RepositoryLoading label="Loading directory" />
  if (!kind)
    return (
      <div role="status" aria-label="Loading path" className="flex items-center gap-3 rounded-lg border bg-card p-4">
        <Folder className="size-4 text-muted-foreground" />
        <Skeleton className="repository-skeleton h-4 w-48" />
        <span className="sr-only">Loading path</span>
      </div>
    )
  return (
    <div role="status" aria-label="Loading file" className="overflow-hidden rounded-lg border bg-card">
      <span className="sr-only">Loading file</span>
      <div aria-hidden="true">
        <div className="flex items-center gap-3 border-b bg-secondary px-4 py-3">
          <FileText className="size-4 text-muted-foreground" />
          <Skeleton className="repository-skeleton h-4 w-36" />
          <Skeleton className="ml-auto h-4 w-16" />
        </div>
        <div className="flex justify-end gap-2 border-b bg-secondary/50 px-4 py-2">
          {[0, 1, 2, 3].map((item) => (
            <Skeleton key={item} className="h-6 w-14" />
          ))}
        </div>
        <div className="overflow-hidden py-4">
          {Array.from({ length: 14 }, (_, index) => (
            <div key={index} className="flex h-6 items-center gap-4">
              <span className="w-12 shrink-0 border-r pr-3 text-right font-mono text-xs text-muted-foreground/50">
                {index + 1}
              </span>
              <Skeleton className={`repository-skeleton h-3 shrink-0 ${widths[index % widths.length]}`} />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default SourceLoading
