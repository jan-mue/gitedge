import { renderHook } from "@testing-library/react"
import { toast } from "sonner"
import { beforeEach, describe, expect, test, vi } from "vitest"

import useCustomToast from "./useCustomToast"

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

describe("useCustomToast", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  test("returns showSuccessToast and showErrorToast functions", () => {
    const { result } = renderHook(() => useCustomToast())

    expect(typeof result.current.showSuccessToast).toBe("function")
    expect(typeof result.current.showErrorToast).toBe("function")
  })

  test("showSuccessToast calls toast.success with correct parameters", () => {
    const { result } = renderHook(() => useCustomToast())

    result.current.showSuccessToast("Operation completed")

    expect(toast.success).toHaveBeenCalledWith("Success!", {
      description: "Operation completed",
    })
  })

  test("showErrorToast calls toast.error with correct parameters", () => {
    const { result } = renderHook(() => useCustomToast())

    result.current.showErrorToast("Something went wrong")

    expect(toast.error).toHaveBeenCalledWith("Something went wrong!", {
      description: "Something went wrong",
    })
  })

  test("showSuccessToast can be called multiple times", () => {
    const { result } = renderHook(() => useCustomToast())

    result.current.showSuccessToast("First success")
    result.current.showSuccessToast("Second success")

    expect(toast.success).toHaveBeenCalledTimes(2)
    expect(toast.success).toHaveBeenNthCalledWith(1, "Success!", {
      description: "First success",
    })
    expect(toast.success).toHaveBeenNthCalledWith(2, "Success!", {
      description: "Second success",
    })
  })

  test("showErrorToast can be called multiple times", () => {
    const { result } = renderHook(() => useCustomToast())

    result.current.showErrorToast("First error")
    result.current.showErrorToast("Second error")

    expect(toast.error).toHaveBeenCalledTimes(2)
  })

  test("handles empty description", () => {
    const { result } = renderHook(() => useCustomToast())

    result.current.showSuccessToast("")
    result.current.showErrorToast("")

    expect(toast.success).toHaveBeenCalledWith("Success!", {
      description: "",
    })
    expect(toast.error).toHaveBeenCalledWith("Something went wrong!", {
      description: "",
    })
  })
})
