interface MarkdownContentProps {
  html: string
}

const MarkdownContent = ({ html }: MarkdownContentProps) => (
  // biome-ignore lint/security/noDangerouslySetInnerHtml: backend renderer escapes raw HTML and rejects unsafe links
  <div className="markdown-body break-words" dangerouslySetInnerHTML={{ __html: html }} />
)

export default MarkdownContent
