import { Skeleton } from "@/components/ui/skeleton"

const RepositoryLoading = ({ label = "Loading repository", rows = 6 }: { label?: string; rows?: number }) => (
  <div role="status" aria-label={label} className="space-y-4 motion-safe:animate-in motion-safe:fade-in-0">
    <span className="sr-only">{label}</span>
    <div className="overflow-hidden rounded-lg border bg-card">
      <div className="flex items-center gap-3 border-b bg-secondary px-4 py-3">
        <Skeleton className="repository-skeleton size-7 rounded-full" />
        <Skeleton className="repository-skeleton h-4 w-1/3" />
        <Skeleton className="repository-skeleton ml-auto h-4 w-20" />
      </div>
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="flex items-center gap-3 border-b px-4 py-3 last:border-0">
          <Skeleton className="repository-skeleton size-4" />
          <Skeleton className={`h-4 ${index % 2 ? "w-1/3" : "w-1/2"}`} />
        </div>
      ))}
    </div>
  </div>
)

export const RepositoryError = ({
  message = "Unable to load this page.",
  retry,
}: {
  message?: string
  retry?: () => void
}) => (
  <div role="alert" className="rounded-lg border bg-card p-8 text-center">
    <p className="text-sm text-muted-foreground">{message}</p>
    {retry && (
      <button
        type="button"
        onClick={retry}
        className="mt-3 rounded border bg-secondary px-3 py-1.5 text-sm hover:bg-accent"
      >
        Try again
      </button>
    )}
  </div>
)

export default RepositoryLoading
