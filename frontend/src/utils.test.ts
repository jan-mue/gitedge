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
  test("calls callback with error message", () => {
    const messages: string[] = []
    const callback = (msg: string) => messages.push(msg)

    handleError.call(callback, new Error("Network Error"))

    expect(messages).toEqual(["Network Error"])
  })

  test("calls callback with detail string from the error body", () => {
    const messages: string[] = []
    const callback = (msg: string) => messages.push(msg)

    handleError.call(callback, { detail: "User not found" })

    expect(messages).toEqual(["User not found"])
  })

  test("calls callback with first validation error message from array", () => {
    const messages: string[] = []
    const callback = (msg: string) => messages.push(msg)
    const error = {
      detail: [
        { msg: "Email is required", loc: ["body", "email"] },
        { msg: "Password too short", loc: ["body", "password"] },
      ],
    }

    handleError.call(callback, error)

    expect(messages).toEqual(["Email is required"])
  })

  test("calls callback with error message when there is no detail", () => {
    const messages: string[] = []
    const callback = (msg: string) => messages.push(msg)

    handleError.call(callback, new Error("Request failed"))

    expect(messages).toEqual(["Request failed"])
  })

  test("calls callback with default message for a non-error value", () => {
    const messages: string[] = []
    const callback = (msg: string) => messages.push(msg)

    handleError.call(callback, { body: {} })

    expect(messages).toEqual(["Something went wrong."])
  })

  test("calls callback with default message for an empty object", () => {
    const messages: string[] = []
    const callback = (msg: string) => messages.push(msg)

    handleError.call(callback, {})

    expect(messages).toEqual(["Something went wrong."])
  })

  test("calls callback with default message when detail is an empty array", () => {
    const messages: string[] = []
    const callback = (msg: string) => messages.push(msg)

    handleError.call(callback, { detail: [] })

    expect(messages).toEqual(["Something went wrong."])
  })
})
