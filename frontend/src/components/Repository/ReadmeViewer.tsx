import { BookOpen } from "lucide-react"

import MarkdownContent from "@/components/Common/MarkdownContent"

interface ReadmeViewerProps {
  html: string
  content: string
  filename?: string
}

const ReadmeViewer = ({ html, content, filename = "README.md" }: ReadmeViewerProps) => {
  return (
    <div className="border border-border rounded-lg mt-4 overflow-hidden" data-testid="readme-viewer">
      <div className="flex items-center gap-2 px-4 py-2.5 bg-secondary border-b border-border">
        <BookOpen className="w-4 h-4 text-muted-foreground" />
        <span className="text-sm font-medium text-foreground">{filename}</span>
      </div>
      <div className="px-6 py-4 bg-card" data-testid="readme-content">
        {html ? (
          <MarkdownContent html={html} />
        ) : (
          <pre className="whitespace-pre-wrap text-sm text-foreground font-mono">{content}</pre>
        )}
      </div>
    </div>
  )
}

export default ReadmeViewer
