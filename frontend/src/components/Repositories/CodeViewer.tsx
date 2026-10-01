import { Link as RouterLink } from "@tanstack/react-router"
import { ArrowLeft, File } from "lucide-react"

import type { FileContent } from "@/client"
import { Button } from "@/components/ui/button"
import { useSyntaxHighlightCSS } from "@/hooks/useSyntaxHighlightCSS"
import { formatSize } from "@/utils"

interface CodeViewerProps {
  file: FileContent
  backLink: {
    owner: string
    repo: string
    searchRef?: string
    path?: string
  }
}

const CodeViewer = ({ file, backLink }: CodeViewerProps) => {
  useSyntaxHighlightCSS(file.css, file.css_dark)

  return (
    <div
      className="file-viewer border rounded-lg overflow-hidden"
      data-testid="file-viewer"
    >
      <FileHeader file={file} backLink={backLink} />
      <HighlightedContent html={file.highlighted_html} />
    </div>
  )
}

const FileHeader = ({
  file,
  backLink,
}: {
  file: FileContent
  backLink: CodeViewerProps["backLink"]
}) => (
  <div className="flex items-center justify-between bg-muted/50 border-b px-4 py-2">
    <div className="flex items-center gap-2 text-sm">
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
    <RouterLink
      to="/$owner/$repo"
      params={{ owner: backLink.owner, repo: backLink.repo }}
      search={{
        ref: backLink.searchRef,
        path: backLink.path || undefined,
      }}
    >
      <Button variant="ghost" size="sm">
        <ArrowLeft className="h-4 w-4 mr-1" />
        Back
      </Button>
    </RouterLink>
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
