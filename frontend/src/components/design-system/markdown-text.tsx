import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

/** Render untrusted model text without accepting raw HTML or loading remote images. */
export const MarkdownText = ({ children }: { children: string }) => (
  <div className="markdown-body break-words">
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      skipHtml
      components={{
        a: ({ children, href }) => (
          <a href={href} target="_blank" rel="noopener noreferrer">
            {children}
          </a>
        ),
        img: ({ alt }) => <span>{alt || "Image"}</span>,
      }}
    >
      {children}
    </ReactMarkdown>
  </div>
)
