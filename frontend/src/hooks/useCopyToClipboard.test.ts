import { act, renderHook } from "@testing-library/react"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { useCopyToClipboard } from "./useCopyToClipboard"

describe("useCopyToClipboard", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  test("initial state has null copiedText", () => {
    const { result } = renderHook(() => useCopyToClipboard())
    const [copiedText] = result.current

    expect(copiedText).toBeNull()
  })

  test("returns a copy function", () => {
    const { result } = renderHook(() => useCopyToClipboard())
    const [, copy] = result.current

    expect(typeof copy).toBe("function")
  })

  test("copies text to clipboard successfully", async () => {
    const { result } = renderHook(() => useCopyToClipboard())

    let success: boolean
    await act(async () => {
      success = await result.current[1]("test text")
    })

    expect(success!).toBe(true)
    expect(result.current[0]).toBe("test text")
  })

  test("clears copied text after 2 seconds", async () => {
    vi.useFakeTimers()

    const { result } = renderHook(() => useCopyToClipboard())

    await act(async () => {
      await result.current[1]("test text")
    })

    expect(result.current[0]).toBe("test text")

    act(() => {
      vi.advanceTimersByTime(2000)
    })

    expect(result.current[0]).toBeNull()

    vi.useRealTimers()
  })
})
