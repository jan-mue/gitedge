import { GitBranch } from "lucide-react"

const FeedLoading = () => (
  <div role="status" aria-label="Loading feed" className="feed-loading space-y-4">
    <span className="sr-only">Loading your activity feed</span>
    <div aria-hidden="true" className="space-y-4">
      {[0, 1, 2].map((card) => (
        <div
          key={card}
          className="feed-loading-card overflow-hidden rounded-lg border bg-card"
          style={{ animationDelay: `${card * 100}ms` }}
        >
          <div className="flex items-start gap-2 px-4 py-3">
            <div className="feed-loading-avatar flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary/60">
              <GitBranch className="size-4" />
            </div>
            <div className="flex-1">
              <div className="flex h-5 items-center">
                <div className="feed-loading-line h-3 w-2/3 rounded-full bg-muted" />
              </div>
              <div className="flex h-4 items-center">
                <div className="feed-loading-line h-2 w-24 rounded-full bg-muted" />
              </div>
            </div>
            <div className="feed-loading-line size-5 rounded bg-muted" />
          </div>
          <div className="space-y-3 px-4 pb-4">
            <div className={`feed-loading-line h-4 rounded bg-muted ${card % 2 ? "w-1/2" : "w-3/4"}`} />
            <div className="feed-loading-line h-5 w-20 rounded-full bg-muted" />
            <div className="space-y-3 rounded-lg bg-secondary p-4">
              <div className="feed-loading-line h-3 w-full rounded-full bg-accent" />
              <div className="feed-loading-line h-3 w-full rounded-full bg-accent" />
              <div className="feed-loading-line h-3 w-4/5 rounded-full bg-accent" />
            </div>
            <div className="feed-loading-line h-3 w-24 rounded bg-muted" />
          </div>
        </div>
      ))}
    </div>
  </div>
)

export const FeedListLoading = ({ label }: { label: string }) => (
  <div role="status" aria-label={label} className="space-y-5 p-4">
    <span className="sr-only">{label}</span>
    {[0, 1, 2].map((row) => (
      <div key={row} aria-hidden="true" className="space-y-2">
        <div className="feed-loading-line h-3 w-3/4 rounded bg-muted" />
        <div className="feed-loading-line h-2 w-1/2 rounded bg-muted" />
      </div>
    ))}
  </div>
)

export default FeedLoading
