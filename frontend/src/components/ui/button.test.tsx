import { describe, expect, test } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { Button, buttonVariants } from "./button"

describe("Button", () => {
  test("renders button with text", () => {
    render(<Button>Click me</Button>)

    expect(screen.getByRole("button", { name: "Click me" })).toBeInTheDocument()
  })

  test("renders as a button element by default", () => {
    render(<Button>Test</Button>)

    const button = screen.getByRole("button")
    expect(button.tagName).toBe("BUTTON")
  })

  test("applies default variant classes", () => {
    render(<Button>Default</Button>)

    const button = screen.getByRole("button")
    expect(button).toHaveClass("bg-primary")
    expect(button).toHaveClass("text-primary-foreground")
  })

  test("applies destructive variant classes", () => {
    render(<Button variant="destructive">Delete</Button>)

    const button = screen.getByRole("button")
    expect(button).toHaveClass("bg-destructive")
  })

  test("applies outline variant classes", () => {
    render(<Button variant="outline">Outline</Button>)

    const button = screen.getByRole("button")
    expect(button).toHaveClass("border")
    expect(button).toHaveClass("bg-background")
  })

  test("applies secondary variant classes", () => {
    render(<Button variant="secondary">Secondary</Button>)

    const button = screen.getByRole("button")
    expect(button).toHaveClass("bg-secondary")
  })

  test("applies ghost variant classes", () => {
    render(<Button variant="ghost">Ghost</Button>)

    const button = screen.getByRole("button")
    expect(button).toHaveClass("hover:bg-accent")
  })

  test("applies link variant classes", () => {
    render(<Button variant="link">Link</Button>)

    const button = screen.getByRole("button")
    expect(button).toHaveClass("text-primary")
    expect(button).toHaveClass("underline-offset-4")
  })

  test("applies small size classes", () => {
    render(<Button size="sm">Small</Button>)

    const button = screen.getByRole("button")
    expect(button).toHaveClass("h-8")
  })

  test("applies large size classes", () => {
    render(<Button size="lg">Large</Button>)

    const button = screen.getByRole("button")
    expect(button).toHaveClass("h-10")
  })

  test("applies icon size classes", () => {
    render(<Button size="icon">Icon</Button>)

    const button = screen.getByRole("button")
    expect(button).toHaveClass("size-9")
  })

  test("handles click events", async () => {
    const user = userEvent.setup()
    let clicked = false
    const handleClick = () => {
      clicked = true
    }

    render(<Button onClick={handleClick}>Click</Button>)

    await user.click(screen.getByRole("button"))
    expect(clicked).toBe(true)
  })

  test("can be disabled", () => {
    render(<Button disabled>Disabled</Button>)

    const button = screen.getByRole("button")
    expect(button).toBeDisabled()
  })

  test("disabled button has correct classes", () => {
    render(<Button disabled>Disabled</Button>)

    const button = screen.getByRole("button")
    expect(button).toHaveClass("disabled:pointer-events-none")
    expect(button).toHaveClass("disabled:opacity-50")
  })

  test("accepts custom className", () => {
    render(<Button className="custom-class">Custom</Button>)

    const button = screen.getByRole("button")
    expect(button).toHaveClass("custom-class")
  })

  test("renders as child element when asChild is true", () => {
    render(
      <Button asChild>
        <a href="/test">Link Button</a>
      </Button>
    )

    const link = screen.getByRole("link", { name: "Link Button" })
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute("href", "/test")
  })

  test("forwards ref to button element", () => {
    let buttonRef: HTMLButtonElement | null = null
    render(
      <Button ref={(ref) => { buttonRef = ref }}>With Ref</Button>
    )

    expect(buttonRef).toBeInstanceOf(HTMLButtonElement)
  })

  test("has data-slot attribute", () => {
    render(<Button>Slot</Button>)

    const button = screen.getByRole("button")
    expect(button).toHaveAttribute("data-slot", "button")
  })

  test("can have type submit", () => {
    render(<Button type="submit">Submit</Button>)

    const button = screen.getByRole("button")
    expect(button).toHaveAttribute("type", "submit")
  })

  test("buttonVariants generates correct classes", () => {
    const classes = buttonVariants({ variant: "destructive", size: "lg" })

    expect(classes).toContain("bg-destructive")
    expect(classes).toContain("h-10")
  })
})
