import { DocsContainer, type DocsContainerProps } from "@storybook/addon-docs/blocks"
import { type PropsWithChildren, useEffect, useSyncExternalStore } from "react"
import { GLOBALS_UPDATED, SET_GLOBALS } from "storybook/internal/core-events"
import { addons } from "storybook/preview-api"
import { create } from "storybook/theming"
import { theme } from "./theme"

const channel = addons.getChannel()
const subscribers = new Set<() => void>()
let selectedTheme = "dark"

// MDX docs without a Canvas need the theme applied explicitly.
const applyTheme = ({ globals }: { globals: { theme?: string } }) => {
  selectedTheme = globals.theme === "light" ? "light" : "dark"
  document.documentElement.classList.toggle("dark", selectedTheme === "dark")
  document.documentElement.classList.toggle("light", selectedTheme === "light")
  for (const notify of subscribers) notify()
}
applyTheme({ globals: { theme: "dark" } })
channel.on(SET_GLOBALS, applyTheme)
channel.on(GLOBALS_UPDATED, applyTheme)

const subscribe = (notify: () => void) => {
  subscribers.add(notify)
  return () => subscribers.delete(notify)
}
const lightTheme = create({ base: "light", fontBase: theme.fontBase, fontCode: theme.fontCode })

export const ThemedDocsContainer = (props: PropsWithChildren<DocsContainerProps>) => {
  const currentTheme = useSyncExternalStore(subscribe, () => selectedTheme)
  useEffect(() => {
    const root = document.querySelector(".sbdocs-wrapper")
    if (!root) return
    const observed = new Set<HTMLElement>()
    const update = (element: HTMLElement) => {
      const scrolls = element.scrollWidth > element.clientWidth + 1 || element.scrollHeight > element.clientHeight + 1
      if (scrolls) {
        element.tabIndex = 0
        element.setAttribute("aria-label", element.tagName === "TABLE" ? "Component properties" : "Component example")
        if (element.tagName !== "TABLE") element.setAttribute("role", "region")
      } else {
        element.removeAttribute("tabindex")
        element.removeAttribute("aria-label")
        if (element.tagName !== "TABLE") element.removeAttribute("role")
      }
    }
    const resize = new ResizeObserver((entries) => {
      for (const entry of entries) update(entry.target as HTMLElement)
    })
    const refresh = () => {
      for (const element of root.querySelectorAll<HTMLElement>(
        ".docs-story, .sbdocs-content table:not(.story-canvas *)",
      )) {
        if (!observed.has(element)) {
          observed.add(element)
          resize.observe(element)
        }
        update(element)
      }
    }
    const mutations = new MutationObserver(refresh)
    mutations.observe(root, { childList: true, subtree: true })
    refresh()
    return () => {
      mutations.disconnect()
      resize.disconnect()
    }
  }, [])
  return <DocsContainer {...props} theme={currentTheme === "dark" ? theme : lightTheme} />
}
