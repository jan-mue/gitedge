export type ActivityView = "pulse" | "contributors" | "code-frequency" | "recent-commits"

const Line = ({ className = "w-full" }: { className?: string }) => (
  <div className={`h-3 rounded bg-muted ${className}`} />
)
const heights = [24, 42, 30, 58, 36, 70, 50, 82, 64, 40, 72, 55]
const ChartLoading = ({
  height = 208,
  frequency = false,
  area = false,
}: {
  height?: number
  frequency?: boolean
  area?: boolean
}) => (
  <div className="relative flex items-end gap-2 border-b border-l border-border px-3 pt-5 pb-3" style={{ height }}>
    <div className="absolute inset-0 flex flex-col justify-around" aria-hidden="true">
      {[0, 1, 2].map((line) => (
        <div key={line} className="border-t border-border/50" />
      ))}
    </div>
    {area ? (
      <svg aria-hidden="true" viewBox="0 0 400 100" preserveAspectRatio="none" className="relative h-full w-full">
        <path
          d="M0 95 L0 70 C25 70 25 35 50 45 S80 80 110 55 S150 65 175 30 S200 60 230 45 S260 15 290 35 S320 65 350 25 S375 50 400 20 L400 100 L0 100 Z"
          fill="var(--muted)"
        />
      </svg>
    ) : (
      heights.map((value, index) => (
        <div key={index} className="relative flex h-full flex-1 flex-col justify-end">
          {frequency ? (
            <>
              <div className="flex h-1/2 items-end">
                <div className="w-full rounded-t bg-muted" style={{ height: `${value}%` }} />
              </div>
              <div className="h-1/2">
                <div className="w-full rounded-b bg-muted/60" style={{ height: `${value / 3}%` }} />
              </div>
            </>
          ) : (
            <div className="rounded-t bg-muted" style={{ height: `${value}%` }} />
          )}
        </div>
      ))
    )}
  </div>
)

const ActivityLoading = ({ view }: { view: ActivityView }) => (
  <div role="status" aria-label="Loading activity" className="space-y-6" data-loading-view={view}>
    <span className="sr-only">Loading activity: {view.replace(/-/g, " ")}</span>
    <div aria-hidden="true" className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Line className="h-6 w-2/3 max-w-96" />
        {(view === "pulse" || view === "contributors") && <Line className="h-8 w-24" />}
      </div>
      {view === "pulse" ? (
        <>
          <div className="feed-loading-card overflow-hidden rounded-lg border">
            <div className="border-b bg-secondary px-4 py-3">
              <div className="h-4 w-20 rounded bg-accent" />
            </div>
            <div className="space-y-4 p-4">
              <div className="grid gap-4 sm:grid-cols-2">
                {[0, 1].map((item) => (
                  <div key={item} className="space-y-2">
                    <Line />
                    <Line className="w-40" />
                  </div>
                ))}
              </div>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                {[0, 1, 2, 3].map((item) => (
                  <div key={item} className="space-y-3 rounded border p-3">
                    <Line className="mx-auto h-6 w-10" />
                    <Line />
                  </div>
                ))}
              </div>
              <div className="flex flex-col gap-4 overflow-hidden rounded-lg border sm:flex-row">
                <div className="flex-1 space-y-3 p-4">
                  <Line />
                  <Line />
                  <Line className="w-4/5" />
                  <Line className="w-2/3" />
                </div>
                <div className="w-full shrink-0 p-2 sm:w-64">
                  <ChartLoading height={112} />
                </div>
              </div>
            </div>
          </div>
          <div className="space-y-3">
            <div className="border-b pb-3">
              <Line className="w-2/3" />
            </div>
            {[0, 1, 2].map((row) => (
              <div key={row} className="flex gap-3">
                <Line className="h-5 w-16" />
                <Line className="w-1/2" />
              </div>
            ))}
          </div>
        </>
      ) : (
        <>
          <div className="feed-loading-card overflow-hidden rounded-lg border p-4">
            {view === "contributors" && <Line className="mx-auto mb-2 h-3 w-2/3" />}
            <ChartLoading
              height={view === "recent-commits" ? 224 : view === "code-frequency" ? 256 : 208}
              frequency={view === "code-frequency"}
              area={view === "contributors"}
            />
          </div>
          {view === "contributors" &&
            [0, 1].map((card) => (
              <div
                key={card}
                className="feed-loading-card overflow-hidden rounded-lg border p-4"
                style={{ animationDelay: `${card * 100}ms` }}
              >
                <div className="mb-3 flex items-center gap-3">
                  <div className="size-10 shrink-0 rounded-full bg-muted" />
                  <div className="flex-1 space-y-2">
                    <Line className="w-32" />
                    <Line className="w-48" />
                  </div>
                  <Line className="h-6 w-8" />
                </div>
                <ChartLoading height={80} />
              </div>
            ))}
        </>
      )}
    </div>
  </div>
)

export default ActivityLoading
