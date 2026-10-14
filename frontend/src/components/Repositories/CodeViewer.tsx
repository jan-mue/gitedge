import { ArrowLeft, File } from "lucide-react"
import { useState } from "react"
import type { CommitInfo, FileContent } from "@/client"
import { Button, ExternalLink, Link } from "@/components/design-system"
import type { SourceMode } from "@/components/Repositories/SourceLink"
import SourceLink from "@/components/Repositories/SourceLink"
import RepositoryCommitHeader from "@/components/Repository/RepositoryCommitHeader"
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard"
import { useSyntaxHighlightCSS } from "@/hooks/useSyntaxHighlightCSS"
import { formatSize } from "@/utils"

interface CodeViewerProps {
  file: FileContent
  commitSha?: string
  lastCommit?: CommitInfo | null
  lastCommitLoading?: boolean
  lastCommitError?: boolean
  onRetryLastCommit?: () => void
  backLink: {
    owner: string
    repo: string
    mode: SourceMode
    refName: string
    path: string
  }
}

const CodeViewer = ({
  file,
  backLink,
  commitSha,
  lastCommit,
  lastCommitLoading,
  lastCommitError,
  onRetryLastCommit,
}: CodeViewerProps) => {
  useSyntaxHighlightCSS(file.css, file.css_dark)
  const [escapedTabs, setEscapedTabs] = useState(false)
  const [, copy] = useCopyToClipboard()
  const revision = backLink.mode === "tag" ? `refs/tags/${backLink.refName}` : backLink.refName
  const rawUrl = `${import.meta.env.VITE_API_URL ?? ""}/api/v1/repositories/${encodeURIComponent(backLink.owner)}/${encodeURIComponent(backLink.repo)}/raw?${new URLSearchParams({ ref: revision, file_path: file.path })}`

  return (
    <div className="file-viewer border rounded-lg overflow-hidden" data-testid="file-viewer">
      <RepositoryCommitHeader
        owner={backLink.owner}
        repo={backLink.repo}
        commit={lastCommit}
        loading={lastCommitLoading}
        error={lastCommitError}
        onRetry={onRetryLastCommit}
      />
      <FileHeader file={file} backLink={backLink} />
      <div className="flex flex-wrap items-center justify-end gap-1 border-b bg-secondary/50 px-4 py-2">
        <ExternalLink href={rawUrl} appearance="codeAction">
          Raw
        </ExternalLink>
        <Link
          to="/$owner/$repo/blame/$"
          params={{ owner: backLink.owner, repo: backLink.repo, _splat: file.path }}
          search={{ ref: revision }}
          appearance="codeAction"
        >
          Blame
        </Link>
        {backLink.mode === "tag" ? (
          <Link
            to="/$owner/$repo/commits/tag/$tag"
            params={{ owner: backLink.owner, repo: backLink.repo, tag: backLink.refName }}
            search={{ path: file.path }}
            appearance="codeAction"
          >
            History
          </Link>
        ) : (
          <Link
            to="/$owner/$repo/commits/branch/$branch"
            params={{ owner: backLink.owner, repo: backLink.repo, branch: backLink.refName }}
            search={{ path: file.path }}
            appearance="codeAction"
          >
            History
          </Link>
        )}

        {commitSha && (
          <SourceLink
            owner={backLink.owner}
            repo={backLink.repo}
            mode="commit"
            refName={commitSha}
            path={file.path}
            appearance="codeAction"
          >
            Permalink
          </SourceLink>
        )}
        <Button type="button" onClick={() => copy(file.content)} variant="codeAction" size="code">
          Copy content
        </Button>
        <Button type="button" onClick={() => setEscapedTabs((value) => !value)} variant="codeAction" size="code">
          {escapedTabs ? "Unescape tabs" : "Escape tabs"}
        </Button>
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
      <Button variant="ghost" size="compact">
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
