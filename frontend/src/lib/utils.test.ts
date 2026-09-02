import { describe, expect, test } from "vitest"

import { cn } from "./utils"

describe("cn", () => {
  test("merges class names", () => {
    expect(cn("foo", "bar")).toBe("foo bar")
  })

  test("handles undefined values", () => {
    expect(cn("foo", undefined, "bar")).toBe("foo bar")
  })

  test("handles null values", () => {
    expect(cn("foo", null, "bar")).toBe("foo bar")
  })

  test("handles false values", () => {
    expect(cn("foo", false, "bar")).toBe("foo bar")
  })

  test("handles empty strings", () => {
    expect(cn("foo", "", "bar")).toBe("foo bar")
  })

  test("handles conditional classes", () => {
    const isActive = true
    const isDisabled = false
    expect(cn("base", isActive && "active", isDisabled && "disabled")).toBe(
      "base active",
    )
  })

  test("handles arrays of classes", () => {
    expect(cn(["foo", "bar"], "baz")).toBe("foo bar baz")
  })

  test("handles object syntax", () => {
    expect(cn({ foo: true, bar: false, baz: true })).toBe("foo baz")
  })

  test("merges tailwind classes correctly (last wins)", () => {
    expect(cn("p-4", "p-2")).toBe("p-2")
  })

  test("merges conflicting tailwind classes", () => {
    expect(cn("text-red-500", "text-blue-500")).toBe("text-blue-500")
  })

  test("preserves non-conflicting tailwind classes", () => {
    expect(cn("p-4", "m-2")).toBe("p-4 m-2")
  })

  test("handles complex tailwind merging", () => {
    expect(cn("px-4 py-2", "px-2")).toBe("py-2 px-2")
  })

  test("returns empty string for no arguments", () => {
    expect(cn()).toBe("")
  })

  test("returns empty string for all falsy arguments", () => {
    expect(cn(undefined, null, false, "")).toBe("")
  })

  test("handles mixed input types", () => {
    expect(
      cn("base", ["array-class"], { "object-class": true }, undefined),
    ).toBe("base array-class object-class")
  })

  test("handles deeply nested arrays", () => {
    expect(cn(["a", ["b", ["c"]]])).toBe("a b c")
  })

  test("handles variant classes from tailwind", () => {
    expect(cn("hover:bg-red-500", "hover:bg-blue-500")).toBe(
      "hover:bg-blue-500",
    )
  })

  test("handles responsive classes", () => {
    expect(cn("md:p-4", "md:p-2")).toBe("md:p-2")
  })

  test("preserves different responsive breakpoints", () => {
    expect(cn("md:p-4", "lg:p-2")).toBe("md:p-4 lg:p-2")
  })
})
