import { ChevronDown, ChevronRight } from "lucide-react"
import { useId, useState } from "react"
import { Button } from "./button"
import { type CheckStatus, CheckStatusIcon } from "./check-status-icon"

export interface LogSection {
  id: string
  name: string
  status: CheckStatus
  log?: string
}

export const LogViewer = ({
  sections,
  log,
  truncated = false,
}: {
  sections: LogSection[]
  log?: string
  truncated?: boolean
}) => {
  const prefix = useId()
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const toggle = (id: string, open: boolean) => setExpanded((old) => ({ ...old, [id]: !open }))
  return (
    <section aria-label="Job logs" className="divide-y divide-border bg-secondary/40">
      {truncated && (
        <p className="px-4 py-2 text-xs text-muted-foreground">
          Showing recent output. Download the log for the complete history.
        </p>
      )}
      {sections.map((section) => {
        const id = `${prefix}-${section.id}`
        const open = expanded[section.id] ?? ["failure", "running"].includes(section.status)
        return (
          <div key={section.id}>
            <Button
              variant="actionStep"
              size="file-row"
              aria-expanded={open}
              aria-controls={id}
              onClick={() => toggle(section.id, open)}
            >
              {open ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
              <CheckStatusIcon status={section.status} />
              <span className="flex-1 text-left">{section.name}</span>
            </Button>
            {open && (
              <pre
                id={id}
                className="max-h-96 overflow-auto whitespace-pre-wrap break-all px-4 py-3 font-mono text-xs text-foreground"
              >
                {section.log || "No log output."}
              </pre>
            )}
          </div>
        )
      })}
      <details className="px-4 py-3 text-sm">
        <summary className="cursor-pointer">Complete job log</summary>
        <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap break-all font-mono text-xs">
          {log || "Waiting for log output…"}
        </pre>
      </details>
    </section>
  )
}
