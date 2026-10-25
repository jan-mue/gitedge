import { defaultRangeExtractor, useVirtualizer, useWindowVirtualizer } from "@tanstack/react-virtual"
import { Check, Columns2, FileCode2, List, Search, WrapText } from "lucide-react"
import { type ReactNode, useCallback, useId, useLayoutEffect, useMemo, useRef, useState } from "react"
import type { CommitFileChange, ReviewLineComment } from "@/client"
import { Button, Input } from "@/components/design-system"
import { DiffFile } from "./DiffFile"
import { useDocumentOffset } from "./diff-virtualization"
import "./diff-viewer.css"

export interface DiffAnnotation extends ReviewLineComment {
  id: string
  author: string
  pending?: boolean
}
export interface DiffSource {
  owner: string
  repo: string
  base: string
  head: string
}
interface DiffViewerProps {
  files: CommitFileChange[]
  additions: number
  deletions: number
  toolbar?: ReactNode
  diffSource?: DiffSource
  reviewedPaths?: string[]
  onReviewed?: (path: string, reviewed: boolean) => void
  reviewBusy?: boolean
  annotations?: DiffAnnotation[]
  onAddComment?: (comment: ReviewLineComment) => Promise<void>
  onDeleteComment?: (id: string) => void
}
const EMPTY_ANNOTATIONS: DiffAnnotation[] = []
const EMPTY_PATHS: string[] = []
const lineCount = (file: CommitFileChange) =>
  file.diff_line_count || (file.hunks ?? []).reduce((sum, hunk) => sum + hunk.lines.length, 0)

const useDiffReviewState = (reviewedPaths: string[], onReviewed?: DiffViewerProps["onReviewed"]) => {
  const [collapsed, setCollapsed] = useState<Map<string, { reviewed: boolean; collapsed: boolean }>>(new Map())
  const [editingPaths, setEditingPaths] = useState<Set<string>>(new Set())
  const reviewed = useMemo(() => new Set(reviewedPaths), [reviewedPaths])
  const isCollapsed = (path: string) => {
    const override = collapsed.get(path)
    return override?.reviewed === reviewed.has(path) ? override.collapsed : reviewed.has(path)
  }
  const onEditorChange = useCallback(
    (path: string, editing: boolean) =>
      setEditingPaths((previous) => {
        if (previous.has(path) === editing) return previous
        const next = new Set(previous)
        if (editing) next.add(path)
        else next.delete(path)
        return next
      }),
    [],
  )
  const toggle = useCallback(
    (path: string) =>
      setCollapsed((previous) => {
        const next = new Map(previous)
        const value = previous.get(path)
        const current = value?.reviewed === reviewed.has(path) ? value.collapsed : reviewed.has(path)
        next.set(path, { reviewed: reviewed.has(path), collapsed: !current })
        return next
      }),
    [reviewed],
  )
  const markReviewed = useCallback(
    (path: string, value: boolean) => {
      setCollapsed((previous) => {
        const next = new Map(previous)
        next.delete(path)
        return next
      })
      onReviewed?.(path, value)
    },
    [onReviewed],
  )
  return { reviewed, editingPaths, isCollapsed, setCollapsed, onEditorChange, toggle, markReviewed }
}
const useDiffViewer = ({
  files,
  reviewedPaths = EMPTY_PATHS,
  onReviewed,
  annotations = EMPTY_ANNOTATIONS,
}: DiffViewerProps) => {
  const id = useId()
  const [filter, setFilter] = useState("")
  const [layout, setLayout] = useState<"unified" | "split">("unified")
  const [wrap, setWrap] = useState(false)
  const [selected, setSelected] = useState(files[0]?.path)
  const listRef = useRef<HTMLDivElement>(null)
  const offset = useDocumentOffset(listRef)
  const visibleFiles = useMemo(
    () => files.filter((file) => file.path.toLowerCase().includes(filter.toLowerCase())),
    [files, filter],
  )
  const byFile = useMemo(() => {
    const map = new Map<string, DiffAnnotation[]>()
    for (const annotation of annotations) {
      const entries = map.get(annotation.path) ?? []
      entries.push(annotation)
      map.set(annotation.path, entries)
    }
    return map
  }, [annotations])
  const { reviewed, editingPaths, isCollapsed, setCollapsed, onEditorChange, toggle, markReviewed } =
    useDiffReviewState(reviewedPaths, onReviewed)
  const useVirtualFiles = visibleFiles.length > 20 || visibleFiles.some((file) => lineCount(file) > 200)
  const virtualizer = useWindowVirtualizer({
    count: visibleFiles.length,
    enabled: useVirtualFiles,
    scrollMargin: offset,
    estimateSize: (index) =>
      isCollapsed(visibleFiles[index].path)
        ? 70
        : 110 + Math.max(1, Math.ceil(lineCount(visibleFiles[index]) / (layout === "split" ? 2 : 1))) * 22,
    getItemKey: (index) => visibleFiles[index].path,
    overscan: 1,
    useAnimationFrameWithResizeObserver: true,
    rangeExtractor: (range) =>
      [
        ...new Set([
          ...defaultRangeExtractor(range),
          ...visibleFiles.flatMap((file, index) => (editingPaths.has(file.path) ? [index] : [])),
        ]),
      ].sort((a, b) => a - b),
  })
  useLayoutEffect(() => {
    if (layout) virtualizer.measure()
  }, [layout, virtualizer])
  const fileId = (path: string) => `${id}-file-${encodeURIComponent(path)}`

  return {
    id,
    filter,
    setFilter,
    layout,
    setLayout,
    wrap,
    setWrap,
    selected,
    setSelected,
    listRef,
    offset,
    visibleFiles,
    byFile,
    reviewed,
    isCollapsed,
    setCollapsed,
    onEditorChange,
    toggle,
    markReviewed,
    useVirtualFiles,
    virtualizer,
    fileId,
  }
}

export const DiffViewer = ({
  files,
  additions,
  deletions,
  toolbar,
  diffSource,
  reviewedPaths = EMPTY_PATHS,
  onReviewed,
  reviewBusy,
  annotations = EMPTY_ANNOTATIONS,
  onAddComment,
  onDeleteComment,
}: DiffViewerProps) => {
  const {
    filter,
    setFilter,
    layout,
    setLayout,
    wrap,
    setWrap,
    selected,
    setSelected,
    listRef,
    offset,
    visibleFiles,
    byFile,
    reviewed,
    isCollapsed,
    setCollapsed,
    onEditorChange,
    toggle,
    markReviewed,
    useVirtualFiles,
    virtualizer,
    fileId,
  } = useDiffViewer({
    files,
    additions,
    deletions,
    toolbar,
    diffSource,
    reviewedPaths,
    onReviewed,
    reviewBusy,
    annotations,
    onAddComment,
    onDeleteComment,
  })
  const renderFile = (file: CommitFileChange) => (
    <DiffFile
      key={file.path}
      file={file}
      id={fileId(file.path)}
      source={diffSource}
      view={{ layout, collapsed: isCollapsed(file.path), onToggle: toggle }}
      review={{
        reviewed: reviewed.has(file.path),
        annotations: byFile.get(file.path),
        onReviewed: onReviewed ? markReviewed : undefined,
        busy: reviewBusy,
        onAddComment,
        onDeleteComment,
        onEditorChange,
      }}
    />
  )
  return (
    <div className="diff-viewer" data-wrap={wrap} data-testid="diff-viewer">
      <div className="diff-toolbar">
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <FileCode2 className="size-4 text-muted-foreground" />
          <strong>
            {files.length} changed {files.length === 1 ? "file" : "files"}
          </strong>
          <span className="font-mono text-success">+{additions}</span>
          <span className="font-mono text-destructive">−{deletions}</span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {onReviewed && (
            <span className="mr-2 text-xs text-muted-foreground">
              {reviewedPaths.length} / {files.length} files viewed
            </span>
          )}
          <fieldset className="flex gap-1" aria-label="Diff layout">
            <Button
              variant="quiet"
              size="compact"
              aria-pressed={layout === "unified"}
              onClick={() => setLayout("unified")}
            >
              <List className="size-4" />
              Unified
            </Button>
            <Button variant="quiet" size="compact" aria-pressed={layout === "split"} onClick={() => setLayout("split")}>
              <Columns2 className="size-4" />
              Split
            </Button>
          </fieldset>
          <Button
            variant="quiet"
            size="icon-sm"
            aria-label="Wrap lines"
            aria-pressed={wrap}
            onClick={() => setWrap(!wrap)}
          >
            <WrapText className="size-4" />
          </Button>
          {toolbar}
        </div>
      </div>
      {!files.length ? (
        <div className="rounded-lg border border-dashed p-10 text-center text-sm text-muted-foreground">
          No changed files in this comparison.
        </div>
      ) : (
        <div className="diff-workspace">
          <nav className="diff-nav" aria-label="Changed files">
            <div className="relative mb-3">
              <Input
                aria-label="Filter changed files"
                placeholder="Filter files…"
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
              />
              <Search className="pointer-events-none absolute right-3 top-2.5 size-4 text-muted-foreground" />
            </div>
            <FileNavigation
              key={filter}
              files={visibleFiles}
              reviewed={reviewed}
              selected={selected}
              onSelect={(file) => {
                setSelected(file.path)
                setCollapsed((previous) => {
                  const next = new Map(previous)
                  next.set(file.path, { reviewed: reviewed.has(file.path), collapsed: false })
                  return next
                })
                if (useVirtualFiles) virtualizer.scrollToIndex(visibleFiles.indexOf(file), { align: "start" })
                else document.getElementById(fileId(file.path))?.scrollIntoView({ behavior: "smooth", block: "start" })
              }}
            />
          </nav>
          <div
            ref={listRef}
            className="diff-files"
            data-virtualized={useVirtualFiles}
            style={useVirtualFiles ? { height: virtualizer.getTotalSize() } : undefined}
          >
            {useVirtualFiles
              ? virtualizer.getVirtualItems().map((item) => (
                  <div
                    key={item.key}
                    ref={virtualizer.measureElement}
                    data-index={item.index}
                    className="diff-virtual-file"
                    style={{ transform: `translateY(${item.start - offset}px)` }}
                  >
                    {renderFile(visibleFiles[item.index])}
                  </div>
                ))
              : visibleFiles.map(renderFile)}
          </div>
        </div>
      )}
    </div>
  )
}

const FileNavigation = ({
  files,
  reviewed,
  selected,
  onSelect,
}: {
  files: CommitFileChange[]
  reviewed: Set<string>
  selected?: string
  onSelect: (file: CommitFileChange) => void
}) => {
  const ref = useRef<HTMLDivElement>(null)
  const enabled = files.length > 100
  const virtualizer = useVirtualizer({
    count: files.length,
    enabled,
    getScrollElement: () => ref.current,
    estimateSize: () => 36,
    overscan: 5,
    initialRect: { width: 240, height: 600 },
  })
  const item = (file: CommitFileChange) => (
    <Button
      key={file.path}
      variant="menu"
      size="branchItem"
      aria-current={selected === file.path ? "true" : undefined}
      onClick={() => onSelect(file)}
    >
      <FileCode2 className="size-4 text-muted-foreground" />
      <span className="min-w-0 flex-1 truncate text-xs" title={file.path}>
        {file.path}
      </span>
      {reviewed.has(file.path) ? (
        <Check className="size-3 text-success" />
      ) : (
        <span className={`diff-status diff-status-${file.change_type}`}>
          {file.change_type === "add"
            ? "+"
            : file.change_type === "delete"
              ? "−"
              : file.change_type === "rename"
                ? "R"
                : "M"}
        </span>
      )}
    </Button>
  )
  return (
    <div ref={ref} className="diff-file-list" data-virtualized={enabled}>
      {enabled ? (
        <div className="diff-nav-spacer" style={{ height: virtualizer.getTotalSize() }}>
          {virtualizer.getVirtualItems().map((row) => (
            <div key={row.key} className="diff-nav-item" style={{ transform: `translateY(${row.start}px)` }}>
              {item(files[row.index])}
            </div>
          ))}
        </div>
      ) : (
        files.map(item)
      )}
      {!files.length && <p className="p-3 text-xs text-muted-foreground">No files match this filter.</p>}
    </div>
  )
}
