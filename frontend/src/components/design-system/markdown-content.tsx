import { useEffect, useRef } from "react"

const MarkdownContent = ({ html }: { html: string }) => {
  const container = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const root = container.current
    if (!root) return
    const update = () => {
      for (const block of root.querySelectorAll<HTMLElement>("pre")) {
        if (block.scrollWidth > block.clientWidth) {
          block.tabIndex = 0
          block.setAttribute("role", "region")
          block.setAttribute("aria-label", "Code block")
        } else {
          block.removeAttribute("tabindex")
          block.removeAttribute("role")
          block.removeAttribute("aria-label")
        }
      }
    }
    update()
    if (typeof ResizeObserver === "undefined") return
    const observer = new ResizeObserver(update)
    observer.observe(root)
    return () => observer.disconnect()
  }, [])
  return (
    // biome-ignore lint/security/noDangerouslySetInnerHtml: backend renderer escapes raw HTML and rejects unsafe links
    <div ref={container} className="markdown-body break-words" dangerouslySetInnerHTML={{ __html: html }} />
  )
}
export default MarkdownContent
