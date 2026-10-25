import { useQuery } from "@tanstack/react-query"
import { defaultRangeExtractor, useWindowVirtualizer } from "@tanstack/react-virtual"
import { ChevronDown, ChevronRight, ExternalLink, FileCode2, Plus } from "lucide-react"
import { Fragment, memo, type ReactNode, useMemo, useRef, useState } from "react"
import type { CommitFileChange, DiffLine, ReviewLineComment } from "@/client"
import { repositoriesGetDiffFileOptions } from "@/client/@tanstack/react-query.gen"
import { Button, Checkbox, CodeSkeleton, ExternalLink as FileLink, Textarea } from "@/components/design-system"
import { DiffCodeRow } from "./DiffCodeRow"
import type { DiffAnnotation, DiffSource } from "./DiffViewer"
import { useDocumentOffset } from "./diff-virtualization"

const labels = { add: "Added", delete: "Deleted", modify: "Modified", rename: "Renamed" }
const EMPTY_ANNOTATIONS: DiffAnnotation[] = []

const CommentEditor = ({
  onSave,
  onCancel,
  body,
  onBodyChange,
}: {
  onSave: (body: string) => Promise<void>
  onCancel: () => void
  body: string
  onBodyChange: (value: string) => void
}) => {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  return (
    <div className="space-y-3 p-4">
      <Textarea
        aria-label="Line comment"
        placeholder="Leave a comment on this line…"
        value={body}
        onChange={(event) => onBodyChange(event.target.value)}
        maxLength={20000}
        autoFocus
      />
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <div className="flex gap-2">
        <Button
          size="compact"
          loading={busy}
          disabled={!body.trim()}
          onClick={async () => {
            setBusy(true)
            setError("")
            try {
              await onSave(body.trim())
            } catch {
              setError("Unable to save this comment. Try again.")
            } finally {
              setBusy(false)
            }
          }}
        >
          Add to review
        </Button>
        <Button size="compact" variant="ghost" disabled={busy} onClick={onCancel}>
          Cancel
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">Only you can see this comment until you submit your review.</p>
    </div>
  )
}

const matchesEditor = (
  editor: { path: string; side: "old" | "new"; line: number } | null,
  path: string,
  side: "old" | "new",
  line: number,
) => editor?.path === path && editor.side === side && editor.line === line

interface DiffFileProps {
  file: CommitFileChange
  id: string
  source?: DiffSource
  view: { collapsed: boolean; layout: "unified" | "split"; onToggle: (path: string) => void }
  review: {
    reviewed: boolean
    annotations?: DiffAnnotation[]
    onEditorChange: (path: string, editing: boolean) => void
    onReviewed?: (path: string, reviewed: boolean) => void
    busy?: boolean
    onAddComment?: (comment: ReviewLineComment) => Promise<void>
    onDeleteComment?: (id: string) => void
  }
}

export const DiffFile = memo(({ file, id, source, view, review }: DiffFileProps) => {
  const { collapsed, layout, onToggle } = view
  const {
    reviewed,
    annotations = EMPTY_ANNOTATIONS,
    onEditorChange,
    onReviewed,
    busy: reviewBusy,
    onAddComment,
    onDeleteComment,
  } = review
  const {
    data: loaded,
    isError,
    refetch,
  } = useQuery({
    ...repositoriesGetDiffFileOptions({
      path: { owner: source?.owner ?? "", repo: source?.repo ?? "" },
      query: { base: source?.base ?? "", head: source?.head ?? "0".repeat(40), file_path: file.path },
    }),
    enabled: file.diff_loaded === false && !!source && !collapsed,
    staleTime: Infinity,
  })
  const data = file.diff_loaded === false ? loaded : file
  const [editor, setEditor] = useState<{ path: string; side: "old" | "new"; line: number } | null>(null)
  const [commentBody, setCommentBody] = useState("")
  const closeEditor = () => {
    setEditor(null)
    setCommentBody("")
    onEditorChange(file.path, false)
  }
  const commentsByLine = useMemo(() => {
    const indexed = new Map<string, DiffAnnotation[]>()
    for (const comment of annotations) {
      const key = `${comment.side}:${comment.line}`
      const entries = indexed.get(key) ?? []
      entries.push(comment)
      indexed.set(key, entries)
    }
    return indexed
  }, [annotations])
  const renderThreadComment = (comment: DiffAnnotation) => (
    <div key={comment.id} className="diff-comment">
      <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>
          <strong className="text-foreground">{comment.author}</strong>
          {comment.pending && " · Pending review"}
        </span>
        {comment.pending && onDeleteComment && (
          <Button variant="textDanger" size="text" onClick={() => onDeleteComment(comment.id)}>
            Remove
          </Button>
        )}
      </div>
      <p className="mt-2 whitespace-pre-wrap text-sm">{comment.body}</p>
    </div>
  )
  const threads = (file: CommitFileChange, line: DiffLine, side: "old" | "new") => {
    const number = side === "old" ? line.old_line : line.new_line
    if (number == null) return null
    const comments = commentsByLine.get(`${side}:${number}`) ?? EMPTY_ANNOTATIONS
    const editing = matchesEditor(editor, file.path, side, number)
    if (!comments.length && !editing) return null
    return (
      <div className="diff-threads">
        {comments.map(renderThreadComment)}
        {editing && onAddComment && (
          <CommentEditor
            body={commentBody}
            onBodyChange={setCommentBody}
            onCancel={closeEditor}
            onSave={async (body) => {
              await onAddComment({ path: file.path, side, line: number, body })
              closeEditor()
            }}
          />
        )}
      </div>
    )
  }

  const cell = (file: CommitFileChange, line: DiffLine | undefined, side?: "old" | "new") => {
    if (!line) return <div className="diff-cell diff-empty" />
    const anchorSide = side ?? (line.kind === "delete" ? "old" : "new")
    const number = anchorSide === "old" ? line.old_line : line.new_line
    return (
      <div className="diff-cell" data-kind={line.kind}>
        <DiffCodeRow
          line={line}
          side={side}
          action={
            onAddComment &&
            number != null && (
              <Button
                variant="ghost"
                size="icon-xs"
                disabled={reviewBusy}
                aria-label={`Comment on ${file.path} ${anchorSide} line ${number}`}
                onClick={() => {
                  setEditor({ path: file.path, side: anchorSide, line: number })
                  onEditorChange(file.path, true)
                }}
              >
                <Plus className="size-3" />
              </Button>
            )
          }
        />
        {line.no_newline && <div className="diff-no-newline">No newline at end of file</div>}
        {side ? (
          threads(file, line, side)
        ) : (
          <>
            {threads(file, line, "old")}
            {threads(file, line, "new")}
          </>
        )}
      </div>
    )
  }
  const renderFileLink = () =>
    source &&
    (file.change_type !== "delete" || source.base) && (
      <FileLink
        href={`/${encodeURIComponent(source.owner)}/${encodeURIComponent(source.repo)}/src/commit/${file.change_type === "delete" ? source.base : source.head}/${file.path.split("/").map(encodeURIComponent).join("/")}`}
        appearance="codeAction"
        data-testid={`view-file-${file.path}`}
        aria-label={`${file.change_type === "delete" ? "View original file" : "View file"} ${file.path}`}
      >
        <ExternalLink className="size-3.5" />
      </FileLink>
    )
  const renderDiffBody = () =>
    !collapsed && (
      <div className="diff-scroll" data-layout={layout}>
        {isError ? (
          <div role="alert" className="p-4 text-sm">
            Unable to load this diff.{" "}
            <Button variant="repository" size="compact" onClick={() => refetch()}>
              Retry
            </Button>
          </div>
        ) : data ? (
          <DiffBody file={data} layout={layout} renderCell={cell} editor={editor} />
        ) : (
          <CodeSkeleton lineCount={Math.ceil((file.diff_line_count ?? 8) / (layout === "split" ? 2 : 1))} />
        )}
      </div>
    )

  return (
    <section
      id={id}
      className="diff-file"
      aria-label={`Diff for ${file.path}`}
      data-testid={`commit-file-${file.path}`}
    >
      <header className="diff-file-header">
        <Button
          variant="ghost"
          size="icon-xs"
          aria-label={`${collapsed ? "Expand" : "Collapse"} ${file.path}`}
          aria-expanded={!collapsed}
          onClick={() => onToggle(file.path)}
        >
          {collapsed ? <ChevronRight className="size-4" /> : <ChevronDown className="size-4" />}
        </Button>
        <FileCode2 className="size-4 shrink-0 text-muted-foreground" />
        <div className="min-w-0 flex-1">
          <span className="break-all font-mono text-xs font-medium">
            {file.old_path && <span className="text-muted-foreground">{file.old_path} → </span>}
            {file.path}
          </span>
        </div>
        <span className={`diff-status diff-status-${file.change_type}`}>{labels[file.change_type]}</span>
        <span className="font-mono text-xs text-success">+{file.additions}</span>
        <span className="font-mono text-xs text-destructive">−{file.deletions}</span>
        {renderFileLink()}
        {onReviewed && (
          <label className="ml-2 flex items-center gap-2 text-xs" htmlFor={`${id}-viewed`}>
            <Checkbox
              id={`${id}-viewed`}
              checked={reviewed}
              disabled={reviewBusy}
              onCheckedChange={(checked) => onReviewed(file.path, checked === true)}
              aria-label={`Mark ${file.path} as viewed`}
            />
            Viewed
          </label>
        )}
      </header>
      {renderDiffBody()}
    </section>
  )
})

type BodyRow = { header: string } | { old?: DiffLine; new?: DiffLine; line?: DiffLine }
const hunkRows = (hunk: NonNullable<CommitFileChange["hunks"]>[number], layout: "unified" | "split"): BodyRow[] => {
  const rows =
    layout === "unified"
      ? hunk.lines.map((line) => ({ line }))
      : hunk.rows.map((row) => ({
          old: row.old == null ? undefined : hunk.lines[row.old],
          new: row.new == null ? undefined : hunk.lines[row.new],
        }))
  return [{ header: hunk.header }, ...rows]
}

const DiffBody = ({
  file,
  layout,
  renderCell,
  editor,
}: {
  editor: { side: "old" | "new"; line: number } | null
  file: CommitFileChange
  layout: "unified" | "split"
  renderCell: (file: CommitFileChange, line: DiffLine | undefined, side?: "old" | "new") => ReactNode
}) => {
  const rows = useMemo(() => (file.hunks ?? []).flatMap((hunk) => hunkRows(hunk, layout)), [file, layout])
  const renderRow = (row: BodyRow) =>
    "header" in row ? (
      <div className="diff-hunk">{row.header}</div>
    ) : layout === "unified" ? (
      renderCell(file, row.line)
    ) : (
      <div className="diff-split-row">
        {renderCell(file, row.old, "old")}
        {renderCell(file, row.new, "new")}
      </div>
    )
  if (!rows.length)
    return (
      <p className="p-6 text-sm text-muted-foreground">
        {file.is_binary
          ? "Binary file changed. No text diff available."
          : "No textual changes (file mode or rename only)."}
      </p>
    )
  const pinned = editor
    ? rows.findIndex(
        (row) =>
          !("header" in row) &&
          (editor.side === "old" ? (row.line ?? row.old)?.old_line : (row.line ?? row.new)?.new_line) === editor.line,
      )
    : -1
  return rows.length > 200 ? (
    <VirtualDiffRows rows={rows} renderRow={renderRow} pinned={pinned} />
  ) : (
    rows.map((row, index) => <Fragment key={index}>{renderRow(row)}</Fragment>)
  )
}

const VirtualDiffRows = ({
  rows,
  renderRow,
  pinned,
}: {
  pinned: number
  rows: BodyRow[]
  renderRow: (row: BodyRow) => ReactNode
}) => {
  const ref = useRef<HTMLDivElement>(null)
  const offset = useDocumentOffset(ref)
  const virtualizer = useWindowVirtualizer({
    count: rows.length,
    estimateSize: (index) => ("header" in rows[index] ? 38 : 22),
    overscan: 12,
    rangeExtractor: (range) =>
      [...new Set([...defaultRangeExtractor(range), ...(pinned >= 0 ? [pinned] : [])])].sort((a, b) => a - b),
    scrollMargin: offset,
    useAnimationFrameWithResizeObserver: true,
  })
  return (
    <div ref={ref} className="diff-virtual-rows" style={{ height: virtualizer.getTotalSize() }}>
      {virtualizer.getVirtualItems().map((item) => (
        <div
          key={item.key}
          data-index={item.index}
          ref={virtualizer.measureElement}
          className="diff-virtual-row"
          style={{ transform: `translateY(${item.start - offset}px)` }}
        >
          {renderRow(rows[item.index])}
        </div>
      ))}
    </div>
  )
}
