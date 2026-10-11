import { Button, Skeleton } from "@/design-system"

const RepositoryLoading = ({ label = "Loading repository", rows = 6 }: { label?: string; rows?: number }) => (
  <div role="status" aria-label={label} className="space-y-4 motion-safe:animate-in motion-safe:fade-in-0">
    <span className="sr-only">{label}</span>
    <div className="overflow-hidden rounded-lg border bg-card">
      <div className="flex items-center gap-3 border-b bg-secondary px-4 py-3">
        <Skeleton appearance="avatar" />
        <Skeleton appearance="third" />
        <Skeleton appearance="trailing" />
      </div>
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="flex items-center gap-3 border-b px-4 py-3 last:border-0">
          <Skeleton appearance="icon" />
          <Skeleton appearance={index % 2 ? "third" : "half"} />
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
      <Button type="button" onClick={retry} variant="outline" size="sm">
        Try again
      </Button>
    )}
  </div>
)

export default RepositoryLoading
