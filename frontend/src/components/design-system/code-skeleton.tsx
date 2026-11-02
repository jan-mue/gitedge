import "./code-skeleton.css"

export const CodeSkeleton = ({
  label = "Loading file diff",
  lineCount = 12,
}: {
  label?: string
  lineCount?: number
}) => (
  <div role="status" aria-label={label} className="code-skeleton" style={{ minHeight: Math.max(176, lineCount * 22) }}>
    <span className="sr-only">{label}</span>
    <div aria-hidden="true" className="code-skeleton-lines">
      {Array.from({ length: Math.min(18, Math.max(8, lineCount)) }, (_, index) => (
        <div key={index} className="code-skeleton-row">
          <span className="code-skeleton-gutter" />
          <span className="code-skeleton-token" />
          <span className="code-skeleton-token" />
        </div>
      ))}
    </div>
  </div>
)
