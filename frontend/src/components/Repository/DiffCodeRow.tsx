import type { ReactNode } from "react"
import type { DiffLine } from "@/client"

/** Renders backend-produced syntax and changed-token ranges without recalculating them. */
export const DiffCodeRow = ({ line, side, action }: { line: DiffLine; side?: "old" | "new"; action?: ReactNode }) => (
  <div className={`diff-code-row ${side ? "diff-single-side" : ""}`}>
    <div className="diff-line-action">{action}</div>
    {!side && <span className="diff-number">{line.old_line}</span>}
    <span className="diff-number">{side === "old" ? line.old_line : line.new_line}</span>
    <span className="diff-sign" aria-hidden="true">
      {line.kind === "add" ? "+" : line.kind === "delete" ? "−" : " "}
    </span>
    <code className="diff-code">
      {line.tokens.length
        ? line.tokens.map((token, index) => (
            <span key={index} data-syntax={token.syntax} data-changed={token.changed ? "true" : undefined}>
              {token.text}
            </span>
          ))
        : " "}
    </code>
  </div>
)
