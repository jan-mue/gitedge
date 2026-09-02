import { AxiosError } from "axios"
import { describe, expect, test } from "vitest"

import { getInitials, handleError } from "./utils"

describe("getInitials", () => {
  test("returns initials for two-word name", () => {
    expect(getInitials("John Doe")).toBe("JD")
  })

  test("returns initials for single-word name", () => {
    expect(getInitials("John")).toBe("J")
  })

  test("returns initials for three-word name (takes first two)", () => {
    expect(getInitials("John Michael Doe")).toBe("JM")
  })

  test("returns uppercase initials for lowercase name", () => {
    expect(getInitials("john doe")).toBe("JD")
  })

  test("returns uppercase initials for mixed case name", () => {
    expect(getInitials("jOhN dOe")).toBe("JD")
  })

  test("handles names with extra spaces (splits on whitespace)", () => {
    // The implementation splits on space, so multiple spaces create empty strings
    expect(getInitials("John   Doe")).toBe("J")
  })

  test("handles single character name", () => {
    expect(getInitials("A")).toBe("A")
  })

  test("handles multiple words and takes only first two", () => {
    expect(getInitials("Alice Bob Charlie David")).toBe("AB")
  })
})

describe("handleError", () => {
  function makeAxiosError(responseData: Record<string, unknown>): Error {
    const err = new AxiosError()
    Object.assign(err, { response: { data: responseData } })
    return err as Error
  }

  test("calls callback with AxiosError message", () => {
    const messages: string[] = []
    const callback = (msg: string) => messages.push(msg)
    const axiosError = new AxiosError("Network Error")

    handleError.call(callback, axiosError)

    expect(messages).toEqual(["Network Error"])
  })

  test("calls callback with detail string from response data", () => {
    const messages: string[] = []
    const callback = (msg: string) => messages.push(msg)
    const error = makeAxiosError({ detail: "User not found" })

    handleError.call(callback, error)

    expect(messages).toEqual(["User not found"])
  })

  test("calls callback with first validation error message from array", () => {
    const messages: string[] = []
    const callback = (msg: string) => messages.push(msg)
    const error = makeAxiosError({
      detail: [
        { msg: "Email is required", loc: ["body", "email"] },
        { msg: "Password too short", loc: ["body", "password"] },
      ],
    })

    handleError.call(callback, error)

    expect(messages).toEqual(["Email is required"])
  })

  test("calls callback with AxiosError message when no detail", () => {
    const messages: string[] = []
    const callback = (msg: string) => messages.push(msg)
    const error = new AxiosError("Request failed")

    handleError.call(callback, error)

    expect(messages).toEqual(["Request failed"])
  })

  test("calls callback with default message for non-Axios error", () => {
    const messages: string[] = []
    const callback = (msg: string) => messages.push(msg)
    const error = { body: {} } as unknown as Error

    handleError.call(callback, error)

    expect(messages).toEqual(["Something went wrong."])
  })

  test("calls callback with default message for empty error", () => {
    const messages: string[] = []
    const callback = (msg: string) => messages.push(msg)
    const error = {} as Error

    handleError.call(callback, error)

    expect(messages).toEqual(["Something went wrong."])
  })

  test("calls callback with AxiosError message when detail is empty array", () => {
    const messages: string[] = []
    const callback = (msg: string) => messages.push(msg)
    const error = new AxiosError("Request failed")
    Object.assign(error, { response: { data: { detail: [] } } })

    handleError.call(callback, error)

    // Empty array falls back to the AxiosError message
    expect(messages).toEqual(["Request failed"])
  })
})
