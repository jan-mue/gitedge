import { useMutation } from "@tanstack/react-query"
import { type ReactNode, useState } from "react"
import { utilsPreviewMarkdownMutation } from "@/client/@tanstack/react-query.gen"
import { Button } from "./button"
import MarkdownContent from "./markdown-content"
import { Textarea } from "./textarea"

export const MarkdownComposer = ({
  value,
  onChange,
  actions,
  label = "Comment",
  testId,
  rows = 5,
}: {
  value: string
  onChange: (value: string) => void
  actions: ReactNode
  label?: string
  testId?: string
  rows?: number
}) => {
  const [tab, setTab] = useState("write")
  const preview = useMutation(utilsPreviewMarkdownMutation())
  const renderEditor = () => (tab === "write" ? "repository" : "quiet")

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card">
      <fieldset className="flex gap-2 border-b border-border bg-secondary px-4 py-2.5" aria-label="Comment editor">
        <Button size="compact" variant={renderEditor()} aria-pressed={tab === "write"} onClick={() => setTab("write")}>
          Write
        </Button>
        <Button
          size="compact"
          variant={tab === "preview" ? "repository" : "quiet"}
          aria-pressed={tab === "preview"}
          onClick={() => {
            setTab("preview")
            preview.mutate({ body: { body: value } })
          }}
        >
          Preview
        </Button>
      </fieldset>
      <div className="p-4">
        {tab === "write" ? (
          <Textarea
            aria-label={label}
            placeholder="Leave a comment"
            rows={rows}
            maxLength={20000}
            value={value}
            onChange={(event) => onChange(event.target.value)}
            data-testid={testId}
          />
        ) : (
          <div className="min-h-32" aria-live="polite">
            {preview.isPending ? (
              "Loading preview…"
            ) : preview.isError ? (
              <p role="alert">Unable to load preview. Select Preview to try again.</p>
            ) : preview.data ? (
              <MarkdownContent html={preview.data} />
            ) : (
              <p className="text-muted-foreground">Nothing to preview.</p>
            )}
          </div>
        )}
        <div className="mt-3 flex flex-wrap justify-end gap-2">{actions}</div>
      </div>
    </div>
  )
}
