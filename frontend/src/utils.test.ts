import { describe, expect, test } from "vitest"

import { handleError } from "./utils"

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
