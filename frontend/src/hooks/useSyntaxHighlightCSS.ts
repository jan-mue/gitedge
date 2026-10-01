import { useEffect } from "react"

/**
 * Injects theme-aware Pygments CSS into the document head.
 *
 * The light CSS is applied at root level, the dark CSS is pre-scoped
 * under `.dark` by the backend so it only takes effect in dark mode.
 * The style element is cleaned up on unmount.
 */
export const useSyntaxHighlightCSS = (css: string, cssDark: string) => {
  useEffect(() => {
    const styleId = "pygments-style"
    let style = document.getElementById(styleId) as HTMLStyleElement | null
    if (!style) {
      style = document.createElement("style")
      style.id = styleId
      document.head.appendChild(style)
    }
    style.textContent = `${css}\n${cssDark}`
    return () => {
      style?.remove()
    }
  }, [css, cssDark])
}
