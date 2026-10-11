import { Link } from "@tanstack/react-router"
import { ArrowLeft, File } from "lucide-react"
import { useState } from "react"

import type { FileContent } from "@/client"
import type { SourceMode } from "@/components/Repositories/SourceLink"
import SourceLink from "@/components/Repositories/SourceLink"
import { Button } from "@/components/ui/button"
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard"
import { useSyntaxHighlightCSS } from "@/hooks/useSyntaxHighlightCSS"
import { formatSize } from "@/utils"

interface CodeViewerProps {
  file: FileContent
  commitSha?: string
  backLink: {
    owner: string
    repo: string
    mode: SourceMode
    refName: string
    path: string
  }
}

const CodeViewer = ({ file, backLink, commitSha }: CodeViewerProps) => {
  useSyntaxHighlightCSS(file.css, file.css_dark)
  const [escapedTabs, setEscapedTabs] = useState(false)
  const [, copy] = useCopyToClipboard()
  const rawUrl = `${import.meta.env.VITE_API_URL ?? ""}/api/v1/repositories/${encodeURIComponent(backLink.owner)}/${encodeURIComponent(backLink.repo)}/raw?${new URLSearchParams({ ref: backLink.refName, file_path: file.path })}`

  return (
    <div className="file-viewer border rounded-lg overflow-hidden" data-testid="file-viewer">
      <FileHeader file={file} backLink={backLink} />
      <div className="flex flex-wrap items-center justify-end gap-1 border-b bg-secondary/50 px-4 py-2">
        <a href={rawUrl} className="rounded border bg-background px-2.5 py-1 text-xs hover:bg-accent">
          Raw
        </a>
        <Link
          to="/$owner/$repo/blame/$"
          params={{ owner: backLink.owner, repo: backLink.repo, _splat: file.path }}
          search={{ ref: backLink.refName }}
          className="rounded border bg-background px-2.5 py-1 text-xs hover:bg-accent"
        >
          Blame
        </Link>
        <Link
          to="/$owner/$repo/commits/branch/$branch"
          params={{ owner: backLink.owner, repo: backLink.repo, branch: backLink.refName }}
          search={{ path: file.path }}
          className="rounded border bg-background px-2.5 py-1 text-xs hover:bg-accent"
        >
          History
        </Link>
        {commitSha && (
          <SourceLink
            owner={backLink.owner}
            repo={backLink.repo}
            mode="commit"
            refName={commitSha}
            path={file.path}
            className="rounded border bg-background px-2.5 py-1 text-xs hover:bg-accent"
          >
            Permalink
          </SourceLink>
        )}
        <button
          type="button"
          onClick={() => copy(file.content)}
          className="rounded border bg-background px-2.5 py-1 text-xs hover:bg-accent"
        >
          Copy content
        </button>
        <button
          type="button"
          onClick={() => setEscapedTabs((value) => !value)}
          className="rounded border bg-background px-2.5 py-1 text-xs hover:bg-accent"
        >
          {escapedTabs ? "Unescape tabs" : "Escape tabs"}
        </button>
      </div>
      <HighlightedContent html={escapedTabs ? file.highlighted_html.replace(/\t/g, "\\t") : file.highlighted_html} />
    </div>
  )
}

const FileHeader = ({ file, backLink }: { file: FileContent; backLink: CodeViewerProps["backLink"] }) => (
  <div className="flex flex-wrap gap-2 items-center justify-between bg-muted/50 border-b px-4 py-2">
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <File className="h-4 w-4 text-muted-foreground" />
      <span className="font-medium" data-testid="file-name">
        {file.name}
      </span>
      <span className="text-muted-foreground">{formatSize(file.size)}</span>
      <span className="text-muted-foreground">{file.line_count} lines</span>
      <span className="text-muted-foreground" data-testid="file-language">
        {file.language}
      </span>
    </div>
    <SourceLink
      owner={backLink.owner}
      repo={backLink.repo}
      mode={backLink.mode}
      refName={backLink.refName}
      path={backLink.path}
    >
      <Button variant="ghost" size="sm">
        <ArrowLeft className="h-4 w-4 mr-1" />
        Back
      </Button>
    </SourceLink>
  </div>
)

const HighlightedContent = ({ html }: { html: string }) => (
  <div
    className="overflow-x-auto text-sm"
    data-testid="highlighted-content"
    // biome-ignore lint/security/noDangerouslySetInnerHtml: Pygments server-rendered HTML
    dangerouslySetInnerHTML={{ __html: html }}
  />
)

export default CodeViewer
