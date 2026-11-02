import { type RefObject, useEffect, useState } from "react"

// Window virtualizers need document coordinates, including headers above the diff.
export const useDocumentOffset = (ref: RefObject<HTMLElement | null>) => {
  const [offset, setOffset] = useState(0)
  useEffect(() => {
    const element = ref.current
    if (!element) return
    let frame = 0
    const measure = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => setOffset(element.getBoundingClientRect().top + window.scrollY))
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(document.body)
    window.addEventListener("resize", measure)
    return () => {
      observer.disconnect()
      window.removeEventListener("resize", measure)
      cancelAnimationFrame(frame)
    }
  }, [ref])
  return offset
}
