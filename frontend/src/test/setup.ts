import "@testing-library/jest-dom/vitest"
import { cleanup } from "@testing-library/react"
import { afterAll, afterEach, beforeAll, vi } from "vitest"
import { client } from "@/client/client.gen"
import { server } from "@/test/server"

afterEach(() => {
  cleanup()
  server.resetHandlers()
  vi.clearAllMocks()
})

beforeAll(() => {
  // Node's fetch requires an absolute URL; use the same origin as jsdom.
  client.setConfig({ baseUrl: window.location.origin })
  server.listen({ onUnhandledFrame: "error" })
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })

  global.ResizeObserver = class {
    observe = vi.fn()
    unobserve = vi.fn()
    disconnect = vi.fn()
  }

  HTMLElement.prototype.hasPointerCapture ??= vi.fn(() => false)
  HTMLElement.prototype.setPointerCapture ??= vi.fn()
  HTMLElement.prototype.releasePointerCapture ??= vi.fn()
  HTMLElement.prototype.scrollIntoView ??= vi.fn()

  global.IntersectionObserver = class {
    observe = vi.fn()
    unobserve = vi.fn()
    disconnect = vi.fn()
    takeRecords = vi.fn(() => [])
    root = null
    rootMargin = ""
    scrollMargin = "0px"
    thresholds = []
  }

  const localStorageMock = {
    getItem: vi.fn(() => null),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
    length: 0,
    key: vi.fn(() => null),
  }
  Object.defineProperty(window, "localStorage", {
    value: localStorageMock,
    writable: true,
  })

  const clipboardMock = {
    writeText: vi.fn().mockResolvedValue(undefined),
    readText: vi.fn().mockResolvedValue(""),
  }
  Object.defineProperty(navigator, "clipboard", {
    value: clipboardMock,
    writable: true,
    configurable: true,
  })
})

afterAll(() => server.close())
